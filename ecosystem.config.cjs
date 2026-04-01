module.exports = {
  apps: [
    {
      name: 'skill-market',
      script: './server/index.js',
      instances: 1,
      autorestart: true,
      watch: false,
      env_production: {
        NODE_ENV: 'production',
      },
    },
  ],
};
