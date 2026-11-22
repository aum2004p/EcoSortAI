import multiprocessing

# Single worker to minimize memory usage on free tier (512MB RAM)
workers = 1
worker_class = "sync"
threads = 1
timeout = 120
keepalive = 2

# Bind
bind = "0.0.0.0:10000"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Preload to share memory across workers
preload_app = True
