const WebSocket = require('ws');

const MCP_SERVER_URL = 'ws://localhost:3000';
const API_KEY = 'mdb_sa_id_68baeeb922d3970b63bba9e7';
const API_SECRET = 'mdb_sa_sk_VneO3QlphelgmBIm4oULVYiZOx5lo8ObPFpVHNQF';

console.log('Connecting to MCP server...');

// Try different authentication methods
const authHeaders = {
  'Authorization': `Bearer ${API_KEY}:${API_SECRET}`,
  'X-API-Key': API_KEY,
  'X-API-Secret': API_SECRET,
  'apiKey': API_KEY,
  'apiSecret': API_SECRET
};

console.log('Trying with Bearer token...');
const ws1 = new WebSocket(MCP_SERVER_URL, {
  headers: {
    'Authorization': `Bearer ${API_KEY}:${API_SECRET}`
  }
});

ws1.on('open', () => {
  console.log('✅ Connected with Bearer token');
  sendQuery(ws1);
});

ws1.on('error', (err) => {
  console.log('❌ Bearer token failed:', err.message);

  console.log('Trying with API key headers...');
  const ws2 = new WebSocket(MCP_SERVER_URL, {
    headers: {
      'X-API-Key': API_KEY,
      'X-API-Secret': API_SECRET
    }
  });

  ws2.on('open', () => {
    console.log('✅ Connected with API key headers');
    sendQuery(ws2);
  });

  ws2.on('error', (err) => {
    console.log('❌ API key headers failed:', err.message);

    console.log('Trying with query parameters...');
    const ws3 = new WebSocket(`${MCP_SERVER_URL}?apiKey=${API_KEY}&apiSecret=${API_SECRET}`);

    ws3.on('open', () => {
      console.log('✅ Connected with query parameters');
      sendQuery(ws3);
    });

    ws3.on('error', (err) => {
      console.log('❌ Query parameters failed:', err.message);
      console.log('All authentication methods failed. The MCP server might not be configured correctly.');
    });

    ws3.on('message', (data) => {
      console.log('Received:', data.toString());
    });
  });

  ws2.on('message', (data) => {
    console.log('Received:', data.toString());
  });
});

ws1.on('message', (data) => {
  console.log('Received:', data.toString());
});

function sendQuery(ws) {
  const query = {
    jsonrpc: '2.0',
    id: 1,
    method: 'find',
    params: {
      database: 'mcp_database',
      collection: 'employees',
      filter: {},
      limit: 5
    }
  };

  console.log('Sending query:', JSON.stringify(query, null, 2));
  ws.send(JSON.stringify(query));
}
