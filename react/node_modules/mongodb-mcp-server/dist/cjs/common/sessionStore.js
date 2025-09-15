"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.SessionStore = void 0;
const logger_js_1 = require("./logger.js");
const managedTimeout_js_1 = require("./managedTimeout.js");
class SessionStore {
    constructor(idleTimeoutMS, notificationTimeoutMS, logger) {
        this.idleTimeoutMS = idleTimeoutMS;
        this.notificationTimeoutMS = notificationTimeoutMS;
        this.logger = logger;
        this.sessions = {};
        if (idleTimeoutMS <= 0) {
            throw new Error("idleTimeoutMS must be greater than 0");
        }
        if (notificationTimeoutMS <= 0) {
            throw new Error("notificationTimeoutMS must be greater than 0");
        }
        if (idleTimeoutMS <= notificationTimeoutMS) {
            throw new Error("idleTimeoutMS must be greater than notificationTimeoutMS");
        }
    }
    getSession(sessionId) {
        this.resetTimeout(sessionId);
        return this.sessions[sessionId]?.transport;
    }
    resetTimeout(sessionId) {
        const session = this.sessions[sessionId];
        if (!session) {
            return;
        }
        session.abortTimeout.restart();
        session.notificationTimeout.restart();
    }
    sendNotification(sessionId) {
        const session = this.sessions[sessionId];
        if (!session) {
            this.logger.warning({
                id: logger_js_1.LogId.streamableHttpTransportSessionCloseNotificationFailure,
                context: "sessionStore",
                message: `session ${sessionId} not found, no notification delivered`,
            });
            return;
        }
        session.logger.info({
            id: logger_js_1.LogId.streamableHttpTransportSessionCloseNotification,
            context: "sessionStore",
            message: "Session is about to be closed due to inactivity",
        });
    }
    setSession(sessionId, transport, logger) {
        const session = this.sessions[sessionId];
        if (session) {
            throw new Error(`Session ${sessionId} already exists`);
        }
        const abortTimeout = (0, managedTimeout_js_1.setManagedTimeout)(async () => {
            if (this.sessions[sessionId]) {
                this.sessions[sessionId].logger.info({
                    id: logger_js_1.LogId.streamableHttpTransportSessionCloseNotification,
                    context: "sessionStore",
                    message: "Session closed due to inactivity",
                });
                await this.closeSession(sessionId);
            }
        }, this.idleTimeoutMS);
        const notificationTimeout = (0, managedTimeout_js_1.setManagedTimeout)(() => this.sendNotification(sessionId), this.notificationTimeoutMS);
        this.sessions[sessionId] = {
            transport,
            abortTimeout,
            notificationTimeout,
            logger,
        };
    }
    async closeSession(sessionId, closeTransport = true) {
        const session = this.sessions[sessionId];
        if (!session) {
            throw new Error(`Session ${sessionId} not found`);
        }
        session.abortTimeout.cancel();
        session.notificationTimeout.cancel();
        if (closeTransport) {
            try {
                await session.transport.close();
            }
            catch (error) {
                this.logger.error({
                    id: logger_js_1.LogId.streamableHttpTransportSessionCloseFailure,
                    context: "streamableHttpTransport",
                    message: `Error closing transport ${sessionId}: ${error instanceof Error ? error.message : String(error)}`,
                });
            }
        }
        delete this.sessions[sessionId];
    }
    async closeAllSessions() {
        await Promise.all(Object.keys(this.sessions).map((sessionId) => this.closeSession(sessionId)));
    }
}
exports.SessionStore = SessionStore;
//# sourceMappingURL=sessionStore.js.map