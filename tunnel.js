const localtunnel = require('localtunnel');

(async () => {
  try {
    const tunnel = await localtunnel({ port: 5000, local_host: '127.0.0.1' });
    console.log("your url is: " + tunnel.url);

    tunnel.on('close', () => {
      console.log("tunnel closed");
      process.exit(1);
    });
  } catch (err) {
    console.error("Failed to establish tunnel:", err);
    process.exit(1);
  }

  // Keep process alive indefinitely
  setInterval(() => {}, 60000);
})();
