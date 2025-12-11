import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to prevent memory leaks
max_requests = 1000
max_requests_jitter = 50

# Logging
errorlog = "/var/log/proenergia/gunicorn_error.log"
loglevel = "info"
accesslog = "/var/log/proenergia/gunicorn_access.log"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "proenergia"

# Daemon mode
daemon = False
pidfile = "/var/run/proenergia/gunicorn.pid"

# User and group to run as
user = "proenergia"
group = "proenergia"

# Server mechanics
preload_app = True
sendfile = True