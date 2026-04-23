
# JupyterLab Configuration for Terminal Support
c = get_config()

# Enable terminals - these are the correct settings for modern JupyterLab
c.ServerApp.terminals_enabled = True
c.TerminalManager.cull_inactive_timeout = 3600
c.TerminalManager.cull_interval = 300

# Allow root user (for Docker containers)
c.ServerApp.allow_root = True

# Terminal settings
c.TerminalManager.shell_command = ['/bin/bash']

# Security settings
c.ServerApp.allow_origin = '*'
c.ServerApp.allow_remote_access = True
c.ServerApp.disable_check_xsrf = True

    # Token/password settings (updated for JupyterLab 4.x)
    c.IdentityProvider.token = ''
    c.ServerApp.password = ''

# IP and port binding
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.open_browser = False
