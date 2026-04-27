module.exports = {
  apps: [
    {
      name: 'skill-market',
      script: './start.sh',
      args: 'production',
      cwd: '.',
      interpreter: 'bash',
      instances: 1,
      autorestart: true,
      watch: false,
    },
  ],
};
