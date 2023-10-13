# README

- Download docker-library release to image
- install git
- entrypoint: config git credential for remote gitea
- health.sh: gitea/portaner/nginx credentials, if have exception output to logs
- use virtualenv for pip install requirements.txt
- create volumes at dockerfile
- EXPOSE port
- process logs should output to docker logs by supervisord 