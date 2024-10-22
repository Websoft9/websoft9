addEventListener('fetch', event => {
    event.respondWith(handleRequest(event.request))
  })
  
  // This data source from: https://raw.githubusercontent.com/Websoft9/doc.websoft9.com/refs/heads/main/docs/reference/_include/dockerhub-proxy.md
  const backends = [
    'https://docker.rainbond.cc',
    'https://docker.1panel.dev',
    'https://docker.fxxk.dedyn.io',
    'https://a.ussh.net',
    'https://docker.zhai.cm'
  ]
  var test = "test"
  
  async function handleRequest(request) {
    // 随机选择一个后端服务器
    const backend = backends[Math.floor(Math.random() * backends.length)]
    
    // 构建新的请求 URL
    const url = new URL(request.url)
    url.hostname = new URL(backend).hostname
    
    // 转发请求到选定的后端服务器
    const modifiedRequest = new Request(url, request)
    const response = await fetch(modifiedRequest)
    return response
  }
  
