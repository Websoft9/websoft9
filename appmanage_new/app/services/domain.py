import time


def app_domain_list(app_id):
    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok[app_domain_list]")
        else:
            raise CommandException(
                const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    domains = get_all_domains(app_id)

    myLogger.info_logger(domains)

    ret = {}
    ret['domains'] = domains

    default_domain = ""
    if domains != None and len(domains) > 0:
        customer_name = app_id.split('_')[1]
        app_url = shell_execute.execute_command_output_all(
            "cat /data/apps/" + customer_name + "/.env")["result"]
        if "APP_URL" in app_url:
            url = shell_execute.execute_command_output_all("cat /data/apps/" + customer_name + "/.env |grep APP_URL=")[
                "result"].rstrip('\n')
            default_domain = url.split('=')[1]
    ret['default_domain'] = default_domain
    myLogger.info_logger(ret)
    return ret


def get_all_domains(app_id):
    customer_name = app_id.split('_')[1]
    domains = []
    token = get_token()
    url = const.NGINX_URL+"/api/nginx/proxy-hosts"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)

    for proxy in response.json():
        portainer_name = proxy["forward_host"]
        if customer_name == portainer_name:
            for domain in proxy["domain_names"]:
                domains.append(domain)
    return domains


def app_proxy_delete(app_id):
    customer_name = app_id.split('_')[1]
    proxy_host = None
    token = get_token()
    url = const.NGINX_URL+"/api/nginx/proxy-hosts"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)

    for proxy in response.json():
        portainer_name = proxy["forward_host"]
        if customer_name == portainer_name:
            proxy_id = proxy["id"]
            token = get_token()
            url = const.NGINX_URL+"/api/nginx/proxy-hosts/" + str(proxy_id)
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            response = requests.delete(url, headers=headers)


def app_domain_delete(app_id, domain):
    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok[app_domain_delete]")
        else:
            raise CommandException(
                const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    if domain is None or domain == "undefined":
        raise CommandException(
            const.ERROR_CLIENT_PARAM_BLANK, "Domains is blank", "")

    old_all_domains = get_all_domains(app_id)
    if domain not in old_all_domains:
        myLogger.info_logger("delete domain is not binded")
        raise CommandException(
            const.ERROR_CLIENT_PARAM_NOTEXIST, "Domain is not bind.", "")

    myLogger.info_logger("Start to delete " + domain)
    proxy = get_proxy_domain(app_id, domain)
    if proxy != None:
        myLogger.info_logger(proxy)
        myLogger.info_logger("before update")
        domains_old = proxy["domain_names"]
        myLogger.info_logger(domains_old)

        domains_old.remove(domain)
        myLogger.info_logger("after update")
        myLogger.info_logger(domains_old)
        if len(domains_old) == 0:
            proxy_id = proxy["id"]
            token = get_token()
            url = const.NGINX_URL+"/api/nginx/proxy-hosts/" + str(proxy_id)
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            response = requests.delete(url, headers=headers)
            try:
                if response.json().get("error"):
                    raise CommandException(
                        const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
            except Exception:
                myLogger.info_logger(response.json())
            set_domain("", app_id)
        else:
            proxy_id = proxy["id"]
            token = get_token()
            url = const.NGINX_URL+"/api/nginx/proxy-hosts/" + str(proxy_id)
            headers = {
                'Authorization': token,
                'Content-Type': 'application/json'
            }
            port = get_container_port(app_id.split('_')[1])
            host = app_id.split('_')[1]
            data = {
                "domain_names": domains_old,
                "forward_scheme": "http",
                "forward_host": host,
                "forward_port": port,
                "access_list_id": "0",
                "certificate_id": 0,
                "meta": {
                    "letsencrypt_agree": False,
                    "dns_challenge": False
                },
                "advanced_config": "",
                "locations": [],
                "block_exploits": False,
                "caching_enabled": False,
                "allow_websocket_upgrade": False,
                "http2_support": False,
                "hsts_enabled": False,
                "hsts_subdomains": False,
                "ssl_forced": False
            }

            response = requests.put(
                url, data=json.dumps(data), headers=headers)
            if response.json().get("error"):
                raise CommandException(
                    const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
            domain_set = app_domain_list(app_id)
            default_domain = domain_set['default_domain']
            # 如果被删除的域名是默认域名，删除后去剩下域名的第一个
            if default_domain == domain:
                set_domain(domains_old[0], app_id)

    else:
        raise CommandException(
            const.ERROR_CLIENT_PARAM_NOTEXIST, "Delete domain is not bind", "")


def app_domain_update(app_id, domain_old, domain_new):
    myLogger.info_logger("app_domain_update")
    domain_list = []
    domain_list.append(domain_old)
    domain_list.append(domain_new)

    check_domains(domain_list)

    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok")
        else:
            raise CommandException(
                const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")
    proxy = get_proxy_domain(app_id, domain_old)
    if proxy != None:
        domains_old = proxy["domain_names"]
        index = domains_old.index(domain_old)
        domains_old[index] = domain_new
        proxy_id = proxy["id"]
        token = get_token()
        url = const.NGINX_URL+"/api/nginx/proxy-hosts/" + str(proxy_id)
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        port = get_container_port(app_id.split('_')[1])
        host = app_id.split('_')[1]
        data = {
            "domain_names": domains_old,
            "forward_scheme": "http",
            "forward_host": host,
            "forward_port": port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": "",
            "locations": [],
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False
        }

        response = requests.put(url, data=json.dumps(data), headers=headers)
        if response.json().get("error"):
            raise CommandException(
                const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
        domain_set = app_domain_list(app_id)
        default_domain = domain_set['default_domain']
        myLogger.info_logger("default_domain=" +
                             default_domain + ",domain_old=" + domain_old)
        # 如果被修改的域名是默认域名，修改后也设置为默认域名
        if default_domain == domain_old:
            set_domain(domain_new, app_id)
    else:
        raise CommandException(
            const.ERROR_CLIENT_PARAM_NOTEXIST, "edit domain is not exist", "")


def app_domain_add(app_id, domain):
    temp_domains = []
    temp_domains.append(domain)
    check_domains(temp_domains)

    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok")
        else:
            raise CommandException(
                const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    old_domains = get_all_domains(app_id)
    if domain in old_domains:
        raise CommandException(
            const.ERROR_CLIENT_PARAM_NOTEXIST, "Domain is in use", "")

    proxy = get_proxy(app_id)
    if proxy != None:
        domains_old = proxy["domain_names"]
        domain_list = domains_old
        domain_list.append(domain)

        proxy_id = proxy["id"]
        token = get_token()
        url = const.NGINX_URL+"/api/nginx/proxy-hosts/" + str(proxy_id)
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        port = get_container_port(app_id.split('_')[1])
        host = app_id.split('_')[1]
        data = {
            "domain_names": domain_list,
            "forward_scheme": "http",
            "forward_host": host,
            "forward_port": port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": "",
            "locations": [],
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False
        }
        response = requests.put(url, data=json.dumps(data), headers=headers)
        if response.json().get("error"):
            raise CommandException(
                const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
    else:
        # 追加
        token = get_token()
        url = const.NGINX_URL+"/api/nginx/proxy-hosts"
        headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        port = get_container_port(app_id.split('_')[1])
        host = app_id.split('_')[1]

        data = {
            "domain_names": temp_domains,
            "forward_scheme": "http",
            "forward_host": host,
            "forward_port": port,
            "access_list_id": "0",
            "certificate_id": 0,
            "meta": {
                "letsencrypt_agree": False,
                "dns_challenge": False
            },
            "advanced_config": "",
            "locations": [],
            "block_exploits": False,
            "caching_enabled": False,
            "allow_websocket_upgrade": False,
            "http2_support": False,
            "hsts_enabled": False,
            "hsts_subdomains": False,
            "ssl_forced": False
        }

        response = requests.post(url, data=json.dumps(data), headers=headers)

        if response.json().get("error"):
            raise CommandException(
                const.ERROR_CONFIG_NGINX, response.json().get("error").get("message"), "")
        set_domain(domain, app_id)

    return domain


def check_domains(domains):
    myLogger.info_logger(domains)
    if domains is None or len(domains) == 0:
        raise CommandException(
            const.ERROR_CLIENT_PARAM_BLANK, "Domains is blank", "")
    else:
        for domain in domains:
            if is_valid_domain(domain):
                if check_real_domain(domain) == False:
                    raise CommandException(
                        const.ERROR_CLIENT_PARAM_NOTEXIST, "Domain and server not match", "")
            else:
                raise CommandException(
                    const.ERROR_CLIENT_PARAM_Format, "Domains format error", "")


def is_valid_domain(domain):
    if domain.startswith("http"):
        return False

    return True


def check_real_domain(domain):
    domain_real = True
    try:
        cmd = "ping -c 1 " + domain + \
            "  | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | uniq"
        domain_ip = shell_execute.execute_command_output_all(cmd)[
            "result"].rstrip('\n')

        ip_result = shell_execute.execute_command_output_all(
            "cat /data/apps/w9services/w9appmanage/public_ip")
        ip_save = ip_result["result"].rstrip('\n')

        if domain_ip == ip_save:
            myLogger.info_logger("Domain check ok!")
        else:
            domain_real = False
    except CommandException as ce:
        domain_real = False

    return domain_real


def get_proxy_domain(app_id, domain):
    customer_name = app_id.split('_')[1]
    proxy_host = None
    token = get_token()
    url = const.NGINX_URL+"/api/nginx/proxy-hosts"
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json'
    }
    response = requests.get(url, headers=headers)

    myLogger.info_logger(response.json())
    for proxy in response.json():
        portainer_name = proxy["forward_host"]
        domain_list = proxy["domain_names"]
        if customer_name == portainer_name:
            myLogger.info_logger("-------------------")
            if domain in domain_list:
                myLogger.info_logger("find the domain proxy")
                proxy_host = proxy
                break

    return proxy_host


def app_domain_set(domain, app_id):
    temp_domains = []
    temp_domains.append(domain)
    check_domains(temp_domains)

    code, message = docker.check_app_id(app_id)
    if code == None:
        info, flag = app_exits_in_docker(app_id)
        if flag:
            myLogger.info_logger("Check app_id ok")
        else:
            raise CommandException(
                const.ERROR_CLIENT_PARAM_NOTEXIST, "APP is not exist", "")
    else:
        raise CommandException(code, message, "")

    set_domain(domain, app_id)


def set_domain(domain, app_id):
    myLogger.info_logger("set_domain start")
    old_domains = get_all_domains(app_id)
    if domain != "":
        if domain not in old_domains:
            message = domain + " is not in use"
            raise CommandException(
                const.ERROR_CLIENT_PARAM_NOTEXIST, message, "")

    customer_name = app_id.split('_')[1]
    app_url = shell_execute.execute_command_output_all(
        "cat /data/apps/" + customer_name + "/.env")["result"]

    if "APP_URL" in app_url:
        myLogger.info_logger("APP_URL is exist")
        if domain == "":
            ip_result = shell_execute.execute_command_output_all(
                "cat /data/apps/w9services/w9appmanage/public_ip")
            domain = ip_result["result"].rstrip('\n')
            cmd = "sed -i 's/APP_URL=.*/APP_URL=" + domain + \
                "/g' /data/apps/" + customer_name + "/.env"
            shell_execute.execute_command_output_all(cmd)
            if "APP_URL_REPLACE=true" in app_url:
                myLogger.info_logger("need up")
                shell_execute.execute_command_output_all(
                    "cd /data/apps/" + customer_name + " && docker compose up -d")
        else:
            cmd = "sed -i 's/APP_URL=.*/APP_URL=" + domain + \
                "/g' /data/apps/" + customer_name + "/.env"
            shell_execute.execute_command_output_all(cmd)
            if "APP_URL_REPLACE=true" in app_url:
                myLogger.info_logger("need up")
                shell_execute.execute_command_output_all(
                    "cd /data/apps/" + customer_name + " && docker compose up -d")
    else:
        myLogger.info_logger("APP_URL is not exist")
        if domain == "":
            ip_result = shell_execute.execute_command_output_all(
                "cat /data/apps/w9services/w9appmanage/public_ip")
            domain = ip_result["result"].rstrip('\n')

        cmd = "sed -i '/APP_NETWORK/a APP_URL=" + domain + \
            "' /data/apps/" + customer_name + "/.env"
        shell_execute.execute_command_output_all(cmd)
    myLogger.info_logger("set_domain success")
