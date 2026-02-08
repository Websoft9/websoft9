import React, { useState, useEffect } from 'react';
import {
  Container,
  Box,
  AppBar,
  Toolbar,
  Typography,
  CircularProgress,
  Alert
} from '@mui/material';
import MediaGrid from './components/MediaGrid';
import CategoryTabs from './components/CategoryTabs';
import { fetchCatalog, fetchProducts, extractCategories } from './utils/api';
import './App.css';

// Feature flag: Set to false to use mock data (Story 5.1), true for real API (Story 5.2)
const USE_REAL_API = true;

function App() {
  const [mediaData, setMediaData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [categories, setCategories] = useState(['all']);

  useEffect(() => {
    fetchMediaData();
  }, []);

  const fetchMediaData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      if (USE_REAL_API) {
        // Story 5.2: Load from nginx-served static JSON files
        try {
          const [catalogData, productsData] = await Promise.all([
            fetchCatalog(),
            fetchProducts()
          ]);
          
          setMediaData(productsData);
          
          // Extract unique categories from product data
          const uniqueCategories = extractCategories(productsData);
          setCategories(uniqueCategories);
          
          setLoading(false);
        } catch (apiError) {
          console.error('API failed, falling back to mock data:', apiError);
          setError(`API Error: ${apiError.message}. Using mock data as fallback.`);
          // Fallback to mock data if API fails
          await loadMockData();
        }
      } else {
        // Story 5.1: Use mock data
        await loadMockData();
      }
    } catch (err) {
      console.error('Failed to load media data:', err);
      setError(err.message || 'Failed to load applications');
      setLoading(false);
    }
  };

  const loadMockData = async () => {
    // Story 5.1: Mock data with comprehensive structure
    const mockData = [
      {
        key: 'wordpress',
        trademark: 'WordPress',
        logo: { imageurl: '/media/logos/wordpress.png' },
        overview: 'Popular open source content management system (CMS)',
        description: '# WordPress\n\nWordPress is a free and open-source CMS...',
        catalogCollection: {
          items: [{ key: 'cms', title: 'CMS' }]
        },
        websiteurl: 'https://wordpress.org',
        tags: ['Blog', 'Website']
      },
      {
        key: 'gitlab',
        trademark: 'GitLab',
        logo: { imageurl: '/media/logos/gitlab.png' },
        overview: 'Complete DevOps platform delivered as a single application',
        description: '# GitLab\n\nGitLab is a web-based DevOps lifecycle tool...',
        catalogCollection: {
          items: [{ key: 'devops', title: 'DevOps' }]
        },
        websiteurl: 'https://gitlab.com',
        tags: ['Git', 'CI/CD']
      },
      {
        key: 'nextcloud',
        trademark: 'Nextcloud',
        logo: { imageurl: '/media/logos/nextcloud.png' },
        overview: 'Self-hosted productivity platform',
        description: '# Nextcloud\n\nNextcloud is a suite of client-server software...',
        catalogCollection: {
          items: [{ key: 'storage', title: 'Storage' }]
        },
        websiteurl: 'https://nextcloud.com',
        tags: ['File Sync', 'Collaboration']
      },
      {
        key: 'mattermost',
        trademark: 'Mattermost',
        logo: { imageurl: '/media/logos/mattermost.png' },
        overview: 'Open source team collaboration platform',
        description: '# Mattermost\n\nMattermost is an open-source, self-hostable...',
        catalogCollection: {
          items: [{ key: 'collaboration', title: 'Collaboration' }]
        },
        websiteurl: 'https://mattermost.com',
        tags: ['Chat', 'Team']
      },
      {
        key: 'mysql',
        trademark: 'MySQL',
        logo: { imageurl: '/media/logos/mysql.png' },
        overview: 'Most popular open source database',
        description: '# MySQL\n\nMySQL is the world\'s most popular open source database...',
        catalogCollection: {
          items: [{ key: 'database', title: 'Database' }]
        },
        websiteurl: 'https://www.mysql.com',
        tags: ['SQL', 'Database']
      },
      {
        key: 'redis',
        trademark: 'Redis',
        logo: { imageurl: '/media/logos/redis.png' },
        overview: 'In-memory data structure store',
        description: '# Redis\n\nRedis is an open source, in-memory data structure...',
        catalogCollection: {
          items: [{ key: 'database', title: 'Database' }]
        },
        websiteurl: 'https://redis.io',
        tags: ['Cache', 'NoSQL']
      },
      {
        key: 'nginx',
        trademark: 'Nginx',
        logo: { imageurl: '/media/logos/nginx.png' },
        overview: 'High-performance web server and reverse proxy',
        description: '# Nginx\n\nNginx is a web server that can also be used as a reverse proxy...',
        catalogCollection: {
          items: [{ key: 'infrastructure', title: 'Infrastructure' }]
        },
        websiteurl: 'https://nginx.org',
        tags: ['Web Server', 'Proxy']
      },
      {
        key: 'grafana',
        trademark: 'Grafana',
        logo: { imageurl: '/media/logos/grafana.png' },
        overview: 'Open source analytics and monitoring solution',
        description: '# Grafana\n\nGrafana is a multi-platform open source analytics...',
        catalogCollection: {
          items: [{ key: 'monitoring', title: 'Monitoring' }]
        },
        websiteurl: 'https://grafana.com',
        tags: ['Dashboard', 'Analytics']
      },
      {
        key: 'jenkins',
        trademark: 'Jenkins',
        logo: { imageurl: '/media/logos/jenkins.png' },
        overview: 'Leading open source automation server',
        description: '# Jenkins\n\nJenkins is a self-contained, open source automation server...',
        catalogCollection: {
          items: [{ key: 'devops', title: 'DevOps' }]
        },
        websiteurl: 'https://www.jenkins.io',
        tags: ['CI/CD', 'Automation']
      },
      {
        key: 'joomla',
        trademark: 'Joomla',
        logo: { imageurl: '/media/logos/joomla.png' },
        overview: 'Award-winning content management system',
        description: '# Joomla\n\nJoomla is a free and open-source content management system...',
        catalogCollection: {
          items: [{ key: 'cms', title: 'CMS' }]
        },
        websiteurl: 'https://www.joomla.org',
        tags: ['Website', 'Portal']
      },
      {
        key: 'drupal',
        trademark: 'Drupal',
        logo: { imageurl: '/media/logos/drupal.png' },
        overview: 'Open source web CMS platform',
        description: '# Drupal\n\nDrupal is a free and open-source web content management framework...',
        catalogCollection: {
          items: [{ key: 'cms', title: 'CMS' }]
        },
        websiteurl: 'https://www.drupal.org',
        tags: ['Enterprise', 'Framework']
      },
      {
        key: 'moodle',
        trademark: 'Moodle',
        logo: { imageurl: '/media/logos/moodle.png' },
        overview: 'Open source learning management system',
        description: '# Moodle\n\nMoodle is a free and open-source learning management system...',
        catalogCollection: {
          items: [{ key: 'education', title: 'Education' }]
        },
        websiteurl: 'https://moodle.org',
        tags: ['LMS', 'E-Learning']
      }
    ];
    
    setMediaData(mockData);
    
    // Extract unique categories
    const uniqueCategories = new Set(['all']);
    mockData.forEach(item => {
      const category = item.catalogCollection?.items?.[0]?.title;
      if (category) {
        uniqueCategories.add(category);
      }
    });
    
    setCategories(Array.from(uniqueCategories));
    setLoading(false);
  };

  const handleCategoryChange = (event, newValue) => {
    setSelectedCategory(newValue);
  };

  const handleItemSelect = (item) => {
    console.log('Selected item:', item);
    // TODO: Open detail modal in future story
  };

  // Filter data by selected category
  const filteredData = selectedCategory === 'all' 
    ? mediaData 
    : mediaData.filter(item => {
        const itemCategory = item.catalogCollection?.items?.[0]?.title;
        return itemCategory === selectedCategory;
      });

  return (
    <div className="App">
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Websoft9 Store
          </Typography>
        </Toolbar>
      </AppBar>

      <Container maxWidth="xl" sx={{ mt: 4, mb: 4 }}>
        {loading && (
          <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
            <CircularProgress />
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {!loading && !error && (
          <>
            <CategoryTabs
              categories={categories}
              selectedCategory={selectedCategory}
              onCategoryChange={handleCategoryChange}
            />

            <MediaGrid
              items={filteredData}
              onItemSelect={handleItemSelect}
            />

            {filteredData.length === 0 && (
              <Box textAlign="center" py={8}>
                <Typography variant="h6" color="text.secondary">
                  No items found in this category
                </Typography>
              </Box>
            )}
          </>
        )}
      </Container>
    </div>
  );
}

export default App;
