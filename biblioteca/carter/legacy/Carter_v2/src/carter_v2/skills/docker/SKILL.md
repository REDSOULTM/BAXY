---
name: docker
description: Docker container and image management — run, build, stop, logs
triggers: [docker, container, contenedor, imagen, image, compose, dockerfile, build, run container, deploy]
requires: {bins: [docker]}
emoji: 🐳
source: builtin
---
# Docker Skill

Use docker via run_command for container management.

## Common operations

### List running containers
```
docker ps
docker ps -a   # include stopped
```

### Start / stop
```
docker start <name_or_id>
docker stop <name_or_id>
docker restart <name_or_id>
```

### Run new container
```
docker run -d --name myapp -p 8080:80 nginx
```

### View logs
```
docker logs <name_or_id>
docker logs -f <name_or_id>   # follow
docker logs --tail 50 <name>
```

### Build image
```
docker build -t myimage:latest .
docker build -t myimage:latest -f path/Dockerfile .
```

### Images
```
docker images
docker pull nginx:latest
docker rmi myimage:latest
```

### Execute command inside container
```
docker exec -it <name> bash
docker exec <name> sh -c "command"
```

### Docker Compose
```
docker compose up -d
docker compose down
docker compose logs -f
docker compose ps
```

## Tips
- Run via run_command; for interactive commands use run_powershell
- Always use -d (detached) for services
- Check Docker Desktop is running first
