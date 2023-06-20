const {
    override,
    addWebpackExternals,
} = require('customize-cra')

module.exports = override(
    addWebpackExternals({
        "cockpit": "cockpit"
    })
)