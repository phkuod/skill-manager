module.exports = {
  apps: [
    {
      name: 'skill-market',
      script: './start.sh',
      args: 'production',
      cwd: __dirname,
      interpreter: 'bash',
      instances: 1,
      autorestart: true,
      watch: false,
    },
  ],
};
