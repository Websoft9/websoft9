"""`PortainerManager`: the only place that talks to Portainer.

Everything the console does to an application - rerun, redeploy, start/stop, remove, read stats -
funnels through these wrappers. Two things matter and are asserted here: the HTTP status a caller
sees (400 for "you asked for something impossible", 500 for "Portainer is broken") and the exact
payload handed to Portainer, because a missing field silently changes what Portainer does.

`PortainerAPI` is replaced with a recorder, so no test needs a Portainer instance.
"""

import json
from types import SimpleNamespace

import pytest

from src.core.exception import CustomException
from src.services import portainer_manager as manager_module
from src.services.portainer_manager import PortainerManager, _extract_portainer_error_message


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        if text is not None:
            self.text = text
        elif payload is None or isinstance(payload, Exception):
            self.text = ''
        else:
            self.text = json.dumps(payload)
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class RecordingPortainerApi:
    """Records every call; unknown methods answer with a configurable response."""

    def __init__(self):
        self.calls = []
        self.responses = {}

    def returns(self, name, response):
        self.responses[name] = response
        return self

    def _respond(self, name, *args, **kwargs):
        self.calls.append({'name': name, 'args': args, 'kwargs': kwargs})
        value = self.responses.get(name, FakeResponse(200, {}))
        if isinstance(value, Exception):
            raise value
        if isinstance(value, list):
            return value.pop(0)
        return value

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return lambda *args, **kwargs: self._respond(name, *args, **kwargs)


@pytest.fixture
def portainer():
    manager = object.__new__(PortainerManager)
    manager.portainer = RecordingPortainerApi()
    return SimpleNamespace(manager=manager, api=manager.portainer)


# ── error message extraction ──────────────────────────────────────────────


def test_an_empty_error_body_gets_a_readable_default():
    assert _extract_portainer_error_message('') == 'Portainer returned an empty error response'


def test_a_plain_text_body_is_kept():
    assert _extract_portainer_error_message('driver failed programming external connectivity') == (
        'driver failed programming external connectivity'
    )


@pytest.mark.parametrize(
    ('body', 'expected'),
    [
        (json.dumps({'details': 'detail text'}), 'detail text'),
        (json.dumps({'message': 'message text'}), 'message text'),
        (json.dumps({'err': 'err text'}), 'err text'),
        (json.dumps({'unrelated': 1}), json.dumps({'unrelated': 1})),
        (json.dumps(['a', 'b']), json.dumps(['a', 'b'])),
    ],
)
def test_structured_errors_prefer_the_most_specific_field(body, expected):
    assert _extract_portainer_error_message(body) == expected


# ── stale compose workspace handling ──────────────────────────────────────


@pytest.mark.parametrize(
    ('message', 'expected'),
    [
        (None, None),
        ('', None),
        ('no path here', None),
        ('mkdir /data/portainer/compose/12: is a directory', '/data/portainer/compose/12'),
    ],
)
def test_compose_workdirs_are_extracted_from_portainer_errors(portainer, message, expected):
    assert portainer.manager._extract_compose_workdir(message) == expected


def test_an_existing_compose_workdir_is_removed(portainer, tmp_path):
    workdir = tmp_path / 'compose' / '12'
    workdir.mkdir(parents=True)

    assert portainer.manager.cleanup_compose_workdir(str(workdir)) is True
    assert not workdir.exists()


@pytest.mark.parametrize('workdir', [None, '', '/nonexistent/compose/12'])
def test_nothing_to_clean_is_not_an_error(portainer, workdir):
    assert portainer.manager.cleanup_compose_workdir(workdir) is False


# ── endpoints and stacks ──────────────────────────────────────────────────


def test_the_local_endpoint_is_the_docker_socket_with_the_smallest_id(portainer):
    portainer.api.returns(
        'get_endpoints',
        FakeResponse(
            200,
            [
                {'Id': 9, 'URL': 'tcp://10.0.0.5:2375'},
                {'Id': 3, 'URL': 'unix:///var/run/docker.sock'},
                {'Id': 1, 'URL': 'unix:///var/run/docker.sock'},
            ],
        ),
    )

    assert portainer.manager.get_local_endpoint_id() == 1


def test_a_missing_local_endpoint_is_a_request_error(portainer):
    portainer.api.returns('get_endpoints', FakeResponse(200, [{'Id': 9, 'URL': 'tcp://10.0.0.5:2375'}]))

    with pytest.raises(CustomException) as error:
        portainer.manager.get_local_endpoint_id()

    assert error.value.status_code == 400
    assert error.value.details == 'Local endpoint is not exist'


def test_a_failing_endpoint_listing_is_a_server_error(portainer):
    portainer.api.returns('get_endpoints', FakeResponse(500, text='down'))

    with pytest.raises(CustomException) as error:
        portainer.manager.get_local_endpoint_id()

    assert error.value.status_code == 500


@pytest.mark.parametrize(('status', 'expected'), [(200, True), (404, False)])
def test_endpoint_existence(portainer, status, expected):
    portainer.api.returns('get_endpoint_by_id', FakeResponse(status, {}))

    assert portainer.manager.check_endpoint_exists(1) is expected


def test_an_endpoint_check_failure_is_a_server_error(portainer):
    portainer.api.returns('get_endpoint_by_id', FakeResponse(500, text='down'))

    with pytest.raises(CustomException) as error:
        portainer.manager.check_endpoint_exists(1)

    assert error.value.status_code == 500


def test_stack_existence_is_matched_by_name(portainer):
    portainer.api.returns('get_stacks', FakeResponse(200, [{'Name': 'wordpress_abc'}]))

    assert portainer.manager.check_stack_exists('wordpress_abc', 1) is True
    assert portainer.manager.check_stack_exists('other', 1) is False


def test_stack_lookup_returns_the_stack_or_none(portainer):
    portainer.api.returns('get_stacks', FakeResponse(200, [{'Name': 'wordpress_abc', 'Id': 8}]))

    assert portainer.manager.get_stack_by_name('wordpress_abc', 1) == {'Name': 'wordpress_abc', 'Id': 8}
    assert portainer.manager.get_stack_by_name('missing', 1) is None


def test_listing_failures_are_server_errors(portainer):
    for name in ('get_stacks', 'get_stack_by_id', 'get_containers'):
        portainer.api.returns(name, FakeResponse(500, text='down'))

    for call in (lambda: portainer.manager.get_stacks(1), lambda: portainer.manager.get_stack_by_id(8)):
        with pytest.raises(CustomException) as error:
            call()
        assert error.value.status_code == 500

    with pytest.raises(CustomException) as error:
        portainer.manager.get_containers(1)
    assert error.value.status_code == 500


def test_containers_of_a_stack_are_returned(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}]))

    assert portainer.manager.get_containers_by_stack_name('wordpress_abc', 1) == [{'Id': 'c1'}]

    portainer.api.returns('get_containers_by_stackName', FakeResponse(500, text='down'))
    with pytest.raises(CustomException) as error:
        portainer.manager.get_containers_by_stack_name('wordpress_abc', 1)
    assert error.value.status_code == 500


# ── create / update / redeploy ────────────────────────────────────────────


def test_stack_creation_returns_the_created_stack(portainer):
    portainer.api.returns('create_stack_standlone_repository', FakeResponse(200, {'Id': 8}))

    result = portainer.manager.create_stack_from_repository('wordpress_abc', 1, 'http://git/x.git', 'u', 'p')

    assert result == {'Id': 8}
    assert portainer.api.calls[0]['args'] == ('wordpress_abc', 1, 'http://git/x.git', 'u', 'p')


def test_stack_creation_failures_keep_the_portainer_message(portainer):
    portainer.api.returns(
        'create_stack_standlone_repository',
        FakeResponse(400, text=json.dumps({'details': 'invalid compose file'})),
    )

    with pytest.raises(CustomException) as error:
        portainer.manager.create_stack_from_repository('wordpress_abc', 1, 'http://git/x.git', 'u', 'p')

    assert error.value.status_code == 400
    assert error.value.details == 'invalid compose file'


def test_a_stale_compose_workspace_is_cleaned_and_the_creation_retried(portainer, monkeypatch):
    portainer.api.returns(
        'create_stack_standlone_repository',
        [
            FakeResponse(400, text='mkdir /data/portainer/compose/12: is a directory'),
            FakeResponse(200, {'Id': 8}),
        ],
    )
    cleaned = []
    monkeypatch.setattr(portainer.manager, 'cleanup_compose_workdir', lambda workdir: cleaned.append(workdir) or True)

    result = portainer.manager.create_stack_from_repository('wordpress_abc', 1, 'http://git/x.git', 'u', 'p')

    assert result == {'Id': 8}
    assert cleaned == ['/data/portainer/compose/12']
    # 重试必须用完全相同的参数
    first, second = portainer.api.calls
    assert first['args'] == second['args']


def test_creation_is_not_retried_when_the_workspace_cannot_be_cleaned(portainer, monkeypatch):
    portainer.api.returns(
        'create_stack_standlone_repository',
        FakeResponse(400, text='mkdir /data/portainer/compose/12: is a directory'),
    )
    monkeypatch.setattr(portainer.manager, 'cleanup_compose_workdir', lambda workdir: False)

    with pytest.raises(CustomException) as error:
        portainer.manager.create_stack_from_repository('wordpress_abc', 1, 'http://git/x.git', 'u', 'p')

    assert len(portainer.api.calls) == 1
    assert 'is a directory' in error.value.details


def test_a_failing_retry_reports_the_second_error(portainer, monkeypatch):
    portainer.api.returns(
        'create_stack_standlone_repository',
        [
            FakeResponse(400, text='mkdir /data/portainer/compose/12: is a directory'),
            FakeResponse(500, text='portainer exploded'),
        ],
    )
    monkeypatch.setattr(portainer.manager, 'cleanup_compose_workdir', lambda workdir: True)

    with pytest.raises(CustomException) as error:
        portainer.manager.create_stack_from_repository('wordpress_abc', 1, 'http://git/x.git', 'u', 'p')

    assert error.value.details == 'portainer exploded'


def test_redeploy_passes_the_credentials_through(portainer):
    portainer.api.returns('redeploy_stack', FakeResponse(200, {}))

    assert portainer.manager.redeploy_stack(8, 1, True, 'git', 'secret') is None
    assert portainer.api.calls[0]['args'] == (8, 1, True, 'git', 'secret')


def test_redeploy_failures_prefer_the_details_field(portainer):
    portainer.api.returns(
        'redeploy_stack',
        FakeResponse(500, text=json.dumps({'details': 'pull access denied', 'message': 'ignored'})),
    )

    with pytest.raises(CustomException) as error:
        portainer.manager.redeploy_stack(8, 1, False, 'git', 'secret')

    assert error.value.status_code == 400
    assert error.value.details == 'pull access denied'


def test_redeploy_wraps_a_transport_failure(portainer):
    portainer.api.returns('redeploy_stack', ConnectionError('connection reset'))

    with pytest.raises(CustomException) as error:
        portainer.manager.redeploy_stack(8, 1, False, 'git', 'secret')

    assert error.value.status_code == 400
    assert error.value.details == 'connection reset'


def test_git_config_updates_forward_every_option(portainer):
    portainer.api.returns('update_stack_git', FakeResponse(200, {'Id': 8}))

    result = portainer.manager.update_stack_git_config(
        stack_id=8,
        endpoint_id=1,
        repository_url='http://git/x.git',
        repository_reference_name='refs/heads/main',
        config_file_path='docker-compose.yml',
        repository_authentication=True,
        repository_username='git',
        repository_password='secret',
        tls_skip_verify=True,
        env=[{'name': 'A', 'value': '1'}],
        additional_files=[{'name': 'f'}],
        prune=True,
    )

    assert result == {'Id': 8}
    kwargs = portainer.api.calls[0]['kwargs']
    assert kwargs['env'] == [{'name': 'A', 'value': '1'}]
    # Portainer 的字段名是 additionalFiles(驼峰)
    assert kwargs['additionalFiles'] == [{'name': 'f'}]
    assert kwargs['prune'] is True


def test_git_config_update_failures_are_reported(portainer):
    portainer.api.returns('update_stack_git', FakeResponse(400, text=json.dumps({'details': 'bad ref'})))

    with pytest.raises(CustomException) as error:
        portainer.manager.update_stack_git_config(8, 1, 'http://git/x.git', '', 'docker-compose.yml', False, '', '', False)

    assert error.value.details == 'bad ref'


def test_legacy_git_settings_are_rewritten_in_place(portainer, monkeypatch):
    monkeypatch.setattr(
        manager_module,
        'normalize_runtime_git_url',
        lambda url: url.replace('websoft9-git:3000', '127.0.0.1:3001'),
    )
    portainer.api.returns(
        'get_stacks',
        FakeResponse(
            200,
            [
                {'Id': 1, 'Name': 'needs-rewrite', 'GitConfig': {'URL': 'http://websoft9-git:3000/git/x.git'}},
                {'Id': 2, 'Name': 'already-ok', 'GitConfig': {'URL': 'http://127.0.0.1:3001/git/y.git'}},
                {'Id': 3, 'Name': 'no-repository'},
            ],
        ),
    )
    portainer.api.returns('update_stack_git', FakeResponse(200, {'Id': 1}))

    result = portainer.manager.rewrite_legacy_stack_git_settings(1)

    assert result == {'matched': 1, 'updated': 1, 'skipped': 2, 'total': 3}
    # update_stack_git_config 把位置参数原样转给 Portainer:
    # (stack_id, endpoint_id, url, ref, config_file, auth, user, password, tls_skip_verify)
    update = portainer.api.calls[1]
    assert update['name'] == 'update_stack_git'
    assert update['args'][2] == 'http://127.0.0.1:3001/git/x.git'
    assert update['args'][4] == 'docker-compose.yml'
    assert update['args'][5] is False


# ── removal ───────────────────────────────────────────────────────────────


def test_stack_removal_accepts_only_204(portainer):
    portainer.api.returns('remove_stack', FakeResponse(204))
    assert portainer.manager.remove_stack(8, 1) is None

    portainer.api.returns('remove_stack', FakeResponse(200, text='still there'))
    with pytest.raises(CustomException):
        portainer.manager.remove_stack(8, 1)


def test_volumes_are_filtered_by_compose_project_label(portainer):
    portainer.api.returns(
        'get_volumes',
        FakeResponse(
            200,
            {
                'Volumes': [
                    {'Name': 'v1', 'Labels': {'com.docker.compose.project': 'wordpress_abc'}},
                    {'Name': 'v2', 'Labels': {'com.docker.compose.project': 'other'}},
                    {'Name': 'v3'},
                    'not-a-dict',
                ]
            },
        ),
    )

    assert portainer.manager.get_volumes_by_stack_name('wordpress_abc', 1, True) == [
        {'Name': 'v1', 'Labels': {'com.docker.compose.project': 'wordpress_abc'}}
    ]


def test_a_malformed_volume_listing_is_wrapped(portainer):
    portainer.api.returns('get_volumes', FakeResponse(200, ValueError('not json')))

    with pytest.raises(CustomException) as error:
        portainer.manager.get_volumes_by_stack_name('wordpress_abc', 1, True)

    assert error.value.status_code == 500


def test_stack_and_volume_removal_removes_both(portainer):
    portainer.api.returns('get_stack_by_id', FakeResponse(200, {'Id': 8, 'Name': 'wordpress_abc'}))
    portainer.api.returns('remove_stack', FakeResponse(204))
    portainer.api.returns(
        'get_volumes',
        FakeResponse(200, {'Volumes': [{'Name': 'v1', 'Labels': {'com.docker.compose.project': 'wordpress_abc'}}]}),
    )
    portainer.api.returns('remove_volume_by_name', FakeResponse(204))

    portainer.manager.remove_stack_and_volumes(8, 1)

    names = [call['args'][1] for call in portainer.api.calls if call['name'] == 'remove_volume_by_name']
    assert names == ['v1']


def test_a_failing_stack_removal_stops_before_the_volumes(portainer):
    portainer.api.returns('get_stack_by_id', FakeResponse(200, {'Id': 8, 'Name': 'wordpress_abc'}))
    portainer.api.returns('remove_stack', FakeResponse(500, text='busy'))

    with pytest.raises(CustomException):
        portainer.manager.remove_stack_and_volumes(8, 1)

    assert not any(call['name'] == 'get_volumes' for call in portainer.api.calls)


def test_a_failing_volume_removal_is_reported(portainer):
    portainer.api.returns('get_stack_by_id', FakeResponse(200, {'Id': 8, 'Name': 'wordpress_abc'}))
    portainer.api.returns('remove_stack', FakeResponse(204))
    portainer.api.returns(
        'get_volumes',
        FakeResponse(200, {'Volumes': [{'Name': 'v1', 'Labels': {'com.docker.compose.project': 'wordpress_abc'}}]}),
    )
    portainer.api.returns('remove_volume_by_name', FakeResponse(409, text='in use'))

    with pytest.raises(CustomException):
        portainer.manager.remove_stack_and_volumes(8, 1)


def test_dangling_volume_cleanup_removes_every_volume_of_the_stack(portainer):
    portainer.api.returns(
        'get_volumes',
        FakeResponse(
            200,
            {
                'Volumes': [
                    {'Name': 'v1', 'Labels': {'com.docker.compose.project': 'wordpress_abc'}},
                    {'Name': 'v2', 'Labels': {'com.docker.compose.project': 'wordpress_abc'}},
                ]
            },
        ),
    )
    portainer.api.returns('remove_volume_by_name', FakeResponse(204))

    portainer.manager.remove_vloumes('wordpress_abc', 1)

    names = [call['args'][1] for call in portainer.api.calls if call['name'] == 'remove_volume_by_name']
    assert names == ['v1', 'v2']


def test_volume_removal_accepts_only_204(portainer):
    portainer.api.returns('remove_volume_by_name', FakeResponse(204))
    assert portainer.manager.remove_volume(['v1'], 1) is None

    portainer.api.returns('remove_volume_by_name', FakeResponse(500, text='volume is busy'))
    with pytest.raises(CustomException) as error:
        portainer.manager.remove_volume(['v1'], 1)
    assert error.value.status_code == 400
    assert error.value.details == 'volume is busy'


# ── lifecycle ─────────────────────────────────────────────────────────────


def test_up_stack_reports_an_already_running_app(portainer):
    portainer.api.returns('up_stack', FakeResponse(409, text='already up'))

    with pytest.raises(CustomException) as error:
        portainer.manager.up_stack(8, 1)

    assert error.value.status_code == 400
    assert error.value.details == 'The app is already running'


def test_up_stack_accepts_200_only(portainer):
    portainer.api.returns('up_stack', FakeResponse(200))
    assert portainer.manager.up_stack(8, 1) is None

    portainer.api.returns('up_stack', FakeResponse(500, text='boom'))
    with pytest.raises(CustomException) as error:
        portainer.manager.up_stack(8, 1)
    assert error.value.status_code == 500


def test_down_stack_reports_an_already_removed_app(portainer):
    portainer.api.returns('down_stack', FakeResponse(400, text='already down'))

    with pytest.raises(CustomException) as error:
        portainer.manager.down_stack(8, 1)

    assert error.value.details == 'The app is already uninstalled'


def test_stopping_a_stack_stops_every_container(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}, {'Id': 'c2'}]))
    portainer.api.returns('stop_container', FakeResponse(204))

    portainer.manager.stop_stack('wordpress_abc', 1)

    stopped = [call['args'][1] for call in portainer.api.calls if call['name'] == 'stop_container']
    assert stopped == ['c1', 'c2']


def test_already_stopped_containers_are_skipped(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}, {'Id': 'c2'}]))
    portainer.api.returns('stop_container', [FakeResponse(304), FakeResponse(404)])

    portainer.manager.stop_stack('wordpress_abc', 1)

    assert len([call for call in portainer.api.calls if call['name'] == 'stop_container']) == 2


def test_stop_failures_carry_the_container_error(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}]))
    portainer.api.returns('stop_container', FakeResponse(500, text=json.dumps({'details': 'container is paused'})))

    with pytest.raises(CustomException) as error:
        portainer.manager.stop_stack('wordpress_abc', 1)

    assert error.value.status_code == 400
    assert error.value.details == 'container is paused'


def test_a_container_listing_failure_aborts_the_lifecycle_action(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(500, text='down'))

    with pytest.raises(CustomException) as error:
        portainer.manager.start_stack('wordpress_abc', 1)

    assert error.value.status_code == 500


def test_starting_a_stack_starts_every_container(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}]))
    portainer.api.returns('start_container', FakeResponse(204))

    portainer.manager.start_stack('wordpress_abc', 1)

    assert [call['name'] for call in portainer.api.calls] == ['get_containers_by_stackName', 'start_container']


def test_restarting_a_stack_restarts_every_container(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}, {'Id': 'c2'}]))
    portainer.api.returns('restart_container', FakeResponse(204))

    portainer.manager.restart_stack('wordpress_abc', 1)

    restarted = [call['args'][1] for call in portainer.api.calls if call['name'] == 'restart_container']
    assert restarted == ['c1', 'c2']


def test_restarting_skips_containers_that_are_gone_or_unchanged(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}, {'Id': 'c2'}, {'Id': 'c3'}]))
    portainer.api.returns('restart_container', [FakeResponse(404), FakeResponse(304), FakeResponse(204)])

    # 与 start/stop 一致:404(已不存在)与 304(未变化)不应让整个操作失败
    portainer.manager.restart_stack('wordpress_abc', 1)

    assert len([call for call in portainer.api.calls if call['name'] == 'restart_container']) == 3


def test_restart_failures_carry_the_container_error(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}]))
    portainer.api.returns('restart_container', FakeResponse(500, text=json.dumps({'details': 'no such container'})))

    with pytest.raises(CustomException) as error:
        portainer.manager.restart_stack('wordpress_abc', 1)

    assert error.value.details == 'no such container'


# ── waiting for containers ────────────────────────────────────────────────


def test_waiting_returns_immediately_when_containers_exist(portainer):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, [{'Id': 'c1'}]))

    assert portainer.manager.wait_for_stack_containers('wordpress_abc', 1) == [{'Id': 'c1'}]


def test_waiting_polls_until_containers_appear(portainer, monkeypatch):
    portainer.api.returns(
        'get_containers_by_stackName',
        [FakeResponse(200, []), FakeResponse(200, [{'Id': 'c1'}])],
    )
    slept = []
    monkeypatch.setattr(manager_module.time, 'sleep', lambda seconds: slept.append(seconds))

    assert portainer.manager.wait_for_stack_containers('wordpress_abc', 1, poll_interval=2) == [{'Id': 'c1'}]
    assert slept == [2]


def test_waiting_gives_up_after_the_timeout(portainer, monkeypatch):
    portainer.api.returns('get_containers_by_stackName', FakeResponse(200, []))
    clock = iter([0, 0, 5, 11])
    monkeypatch.setattr(manager_module.time, 'monotonic', lambda: next(clock, 11))
    monkeypatch.setattr(manager_module.time, 'sleep', lambda seconds: None)

    assert portainer.manager.wait_for_stack_containers('wordpress_abc', 1, timeout_seconds=10) == []


# ── container details ─────────────────────────────────────────────────────


def test_container_stats_are_returned(portainer):
    portainer.api.returns('get_container_stats', FakeResponse(200, {'cpu': 1}))

    assert portainer.manager.get_container_stats(1, 'abc') == {'cpu': 1}


def test_a_missing_container_is_a_404(portainer):
    portainer.api.returns('get_container_stats', FakeResponse(404, text='gone'))

    with pytest.raises(CustomException) as error:
        portainer.manager.get_container_stats(1, 'abc')

    assert error.value.status_code == 404
    assert error.value.message == 'Container Not Found'


def test_unavailable_stats_are_a_503(portainer):
    portainer.api.returns('get_container_stats', FakeResponse(500, text='down'))

    with pytest.raises(CustomException) as error:
        portainer.manager.get_container_stats(1, 'abc')

    assert error.value.status_code == 503
    assert 'HTTP 500' in error.value.details


def test_an_unexpected_stats_payload_is_a_503(portainer):
    portainer.api.returns('get_container_stats', FakeResponse(200, ['not', 'a', 'dict']))

    with pytest.raises(CustomException) as error:
        portainer.manager.get_container_stats(1, 'abc')

    assert error.value.details == 'Docker returned an invalid stats response'


def test_container_lookup_returns_the_container(portainer):
    portainer.api.returns('get_container_by_id', FakeResponse(200, {'Id': 'abc'}))
    assert portainer.manager.get_container_by_id(1, 'abc') == {'Id': 'abc'}

    portainer.api.returns('get_container_by_id', FakeResponse(404, text='gone'))
    with pytest.raises(CustomException) as error:
        portainer.manager.get_container_by_id(1, 'abc')
    # 不存在的容器是 404(与 get_container_stats 一致),不是服务器错误
    assert error.value.status_code == 404
    assert error.value.message == 'Container Not Found'

    portainer.api.returns('get_container_by_id', FakeResponse(500, text='down'))
    with pytest.raises(CustomException) as error:
        portainer.manager.get_container_by_id(1, 'abc')
    assert error.value.status_code == 500
