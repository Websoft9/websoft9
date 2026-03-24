const { override } = require('customize-cra');

module.exports = override(
  (config) => {
    config.module.rules.push({
      test: /\.m?js$/,
      resolve: {
        fullySpecified: false,
      },
    });
    return config;
  }
);
