"""Skill install transport (local copy + ssh rsync).

Single entry point: install_skill(src_dir, target_name, user_name).
Raises InstallError(message, http_status) on any failure; views.py maps
the http_status straight onto the JSON response.
"""


class InstallError(Exception):
    def __init__(self, message, http_status=500):
        super().__init__(message)
        self.http_status = http_status
