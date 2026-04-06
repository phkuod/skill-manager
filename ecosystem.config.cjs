module.exports = {
  apps: [
    {
      name: 'skill-market',
      script: 'gunicorn',
      args: 'skill_market.wsgi --bind 0.0.0.0:3000 --workers 2',
      cwd: './backend',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      watch: false,
      env_production: {
        DJANGO_SETTINGS_MODULE: 'skill_market.settings',
        SKILL_REPO_PATH: '../skill_repo',
        DEBUG: 'False',
        ALLOWED_HOSTS: 'localhost,127.0.0.1',
      },
    },
  ],
};
