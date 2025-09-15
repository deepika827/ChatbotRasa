const McpClient = require('./mcp_client');

async function testMcpConnection() {
  const client = new McpClient({
    serverUrl: 'ws://localhost:3000',
    apiKey: 'mdb_sa_id_68baeeb922d3970b63bba9e7',
    apiSecret: 'mdb_sa_sk_VneO3QlphelgmBIm4oULVYiZOx5lo8ObPFpVHNQF'
  });

  try {
    console.log('🔌 Connecting to MCP server...');
    await client.connect();

    console.log('📊 Testing find query...');
    const result = await client.find('employees', { limit: 5 });
    console.log('✅ Query result:', JSON.stringify(result, null, 2));

    console.log('📝 Testing insert...');
    const insertResult = await client.insert('employees', {
      name: 'John Doe',
      role: 'Test Employee',
      department: 'IT',
      email: 'john.doe@company.com'
    });
    console.log('✅ Insert result:', JSON.stringify(insertResult, null, 2));

    console.log('🔍 Testing find after insert...');
    const updatedResult = await client.find('employees', { limit: 10 });
    console.log('✅ Updated result:', JSON.stringify(updatedResult, null, 2));

  } catch (error) {
    console.error('❌ MCP Error:', error.message);
  } finally {
    client.disconnect();
  }
}

testMcpConnection();
