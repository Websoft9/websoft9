addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

var backends = [];

async function checkHealth() {
  const healthChecks = backends.map(async url => {
      const start = Date.now();
      try {
          const response = await fetch(url, { method: 'HEAD' });
          const end = Date.now();
          return {
              url,
              healthy: response.ok,
              responseTime: response.ok ? end - start : Infinity
          };
      } catch (error) {
          return {
              url,
              healthy: false,
              responseTime: Infinity
          };
      }
  });

  return await Promise.all(healthChecks);
}

async function handleRequest(request) {
  // 检查健康状态
  const healthResults = await checkHealth();

  // 过滤出健康的后端服务器
  const healthyBackends = healthResults.filter(result => result.healthy);

  if (healthyBackends.length === 0) {
      return new Response('All backend servers are down', { status: 503 });
  }

  // 按响应时间排序健康的后端服务器
  healthyBackends.sort((a, b) => a.responseTime - b.responseTime);

  // 尝试按顺序转发请求到健康的后端服务器
  for (const backend of healthyBackends) {
      try {
          const url = new URL(request.url);
          url.hostname = new URL(backend.url).hostname;
          const modifiedRequest = new Request(url, request);
          const response = await fetch(modifiedRequest);
          if (response.ok) {
              return response;
          }
      } catch (error) {
          console.error(`Failed to fetch from ${backend.url}: ${error}`);
      }
  }

  // 如果所有后端服务器都失败
  return new Response('Failed to fetch from all backends', { status: 502 });
}
