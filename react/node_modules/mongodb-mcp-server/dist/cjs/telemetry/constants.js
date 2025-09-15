"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.MACHINE_METADATA = void 0;
const packageInfo_js_1 = require("../common/packageInfo.js");
/**
 * Machine-specific metadata formatted for telemetry
 */
exports.MACHINE_METADATA = {
    mcp_server_version: packageInfo_js_1.packageInfo.version,
    mcp_server_name: packageInfo_js_1.packageInfo.mcpServerName,
    platform: process.platform,
    arch: process.arch,
    os_type: process.platform,
    os_version: process.version,
};
//# sourceMappingURL=constants.js.map