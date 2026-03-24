const { override } = require('customize-cra');

module.exports = override(
  (config) => {
    config.module.rules.push({
      test: /\.m?js$/,
      resolve: {
        fullySpecified: false,
      },
    });
    
    // Mark cockpit as external - provided by Cockpit environment
    config.externals = {
      cockpit: 'cockpit'
    };
    
    return config;
  }
);
