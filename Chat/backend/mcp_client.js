const WebSocket = require('ws');

class McpClient {
  constructor(options) {
    this.serverUrl = options.serverUrl;
    this.apiKey = options.apiKey;
    this.apiSecret = options.apiSecret;
    this.ws = null;
    this.requestId = 1;
    this.pendingRequests = new Map();
  }

  async connect() {
    return new Promise((resolve, reject) => {
      console.log(`Connecting to MCP server at ${this.serverUrl}...`);

      this.ws = new WebSocket(this.serverUrl, {
        headers: {
          'Authorization': `Bearer ${this.apiKey}:${this.apiSecret}`,
          'X-API-Key': this.apiKey,
          'X-API-Secret': this.apiSecret,
          'Content-Type': 'application/json'
        }
      });

      this.ws.on('open', () => {
        console.log('✅ Connected to MCP server');
        resolve();
      });

      this.ws.on('message', (data) => {
        try {
          const response = JSON.parse(data.toString());
          const requestId = response.id;

          if (this.pendingRequests.has(requestId)) {
            const { resolve, reject } = this.pendingRequests.get(requestId);
            this.pendingRequests.delete(requestId);

            if (response.error) {
              reject(new Error(response.error.message));
            } else {
              resolve(response.result);
            }
          }
        } catch (error) {
          console.error('Error parsing MCP response:', error);
        }
      });

      this.ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      });

      this.ws.on('close', (code, reason) => {
        console.log(`Connection closed: ${code} - ${reason}`);
      });

      // Timeout after 10 seconds
      setTimeout(() => {
        reject(new Error('Connection timeout'));
      }, 10000);
    });
  }

  async query(method, params = {}) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('Not connected to MCP server');
    }

    const request = {
      jsonrpc: '2.0',
      id: this.requestId++,
      method: method,
      params: params
    };

    return new Promise((resolve, reject) => {
      this.pendingRequests.set(request.id, { resolve, reject });
      this.ws.send(JSON.stringify(request));

      // Timeout after 30 seconds
      setTimeout(() => {
        if (this.pendingRequests.has(request.id)) {
          this.pendingRequests.delete(request.id);
          reject(new Error('Request timeout'));
        }
      }, 30000);
    });
  }

  async find(collection, options = {}) {
    const params = {
      database: 'mcp_database',
      collection: collection,
      filter: options.filter || {},
      limit: options.limit || 10
    };

    if (options.projection) {
      params.projection = options.projection;
    }

    return this.query('find', params);
  }

  async insert(collection, documents) {
    const params = {
      database: 'mcp_database',
      collection: collection,
      documents: Array.isArray(documents) ? documents : [documents]
    };

    return this.query('insert', params);
  }

  async update(collection, filter, update, options = {}) {
    const params = {
      database: 'mcp_database',
      collection: collection,
      filter: filter,
      update: update,
      upsert: options.upsert || false
    };

    return this.query('update', params);
  }

  async delete(collection, filter) {
    const params = {
      database: 'mcp_database',
      collection: collection,
      filter: filter
    };

    return this.query('delete', params);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

module.exports = McpClient;
