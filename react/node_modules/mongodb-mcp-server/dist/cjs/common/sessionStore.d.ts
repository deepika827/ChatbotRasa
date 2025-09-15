import type { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import type { LoggerBase } from "./logger.js";
export declare class SessionStore {
    private readonly idleTimeoutMS;
    private readonly notificationTimeoutMS;
    private readonly logger;
    private sessions;
    constructor(idleTimeoutMS: number, notificationTimeoutMS: number, logger: LoggerBase);
    getSession(sessionId: string): StreamableHTTPServerTransport | undefined;
    private resetTimeout;
    private sendNotification;
    setSession(sessionId: string, transport: StreamableHTTPServerTransport, logger: LoggerBase): void;
    closeSession(sessionId: string, closeTransport?: boolean): Promise<void>;
    closeAllSessions(): Promise<void>;
}
//# sourceMappingURL=sessionStore.d.ts.map