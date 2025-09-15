import type { Document } from "mongodb";
import type { NodeDriverServiceProvider } from "@mongosh/service-provider-node-driver";
/**
 * Check if the query plan uses an index
 * @param explainResult The result of the explain query
 * @returns true if an index is used, false if it's a full collection scan
 */
export declare function usesIndex(explainResult: Document): boolean;
/**
 * Generate an error message for index check failure
 */
export declare function getIndexCheckErrorMessage(database: string, collection: string, operation: string): string;
/**
 * Generic function to perform index usage check
 */
export declare function checkIndexUsage(provider: NodeDriverServiceProvider, database: string, collection: string, operation: string, explainCallback: () => Promise<Document>): Promise<void>;
//# sourceMappingURL=indexCheck.d.ts.map