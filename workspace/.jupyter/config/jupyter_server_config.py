
# Jupyter Server Configuration
c = get_config()

# Enable terminals explicitly
c.ServerApp.terminals_enabled = True
c.TerminalManager.cull_inactive_timeout = 3600
c.TerminalManager.cull_interval = 300

# Allow root
c.ServerApp.allow_root = True

# Terminal shell settings
c.TerminalManager.shell_command = ['/bin/bash']

# Network settings
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.allow_origin = '*'
c.ServerApp.allow_remote_access = True
c.ServerApp.disable_check_xsrf = True

    # Authentication (updated for JupyterLab 4.x)
    c.IdentityProvider.token = ''
    c.ServerApp.password = ''
