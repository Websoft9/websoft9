import React, { useState, useEffect, useCallback } from 'react';
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
import FilterBar from './components/FilterBar';
import SecondaryCategoryNav from './components/SecondaryCategoryNav';
import PaginationControls from './components/PaginationControls';
import { fetchCatalog, fetchProducts } from './utils/api';
import { locale } from './i18n';
import './App.css';

// Feature flag: Set to false to use mock data (Story 5.1), true for real API (Story 5.2)
const USE_REAL_API = true;

function App() {
  const [mediaData, setMediaData] = useState([]);
  // eslint-disable-next-line no-unused-vars
  const [catalogData, setCatalogData] = useState([]); // Raw catalog data, kept for reference
  const [primaryCatalog, setPrimaryCatalog] = useState([]); // Restructured primary categories
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Category state
  const [primaryCategory, setPrimaryCategory] = useState('all');
  const [secondaryCategory, setSecondaryCategory] = useState('all');
  
  // Search & Pagination state
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(24);

  const fetchMediaData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      if (USE_REAL_API) {
        // Story 5.2: Load from nginx-served static JSON files
        try {
          const [catalogResult, productsResult] = await Promise.all([
            fetchCatalog(),
            fetchProducts()
          ]);
          
          setCatalogData(catalogResult);
          setMediaData(productsResult);
          
          // Build primary category structure from catalog data
          // catalogResult = array of primary categories
          // Each has linkedFrom.catalogCollection.items = secondary categories
          const catalogItems = Array.isArray(catalogResult) ? catalogResult : catalogResult.items || [];
          const primaryCategories = catalogItems.map(primaryCat => ({
            key: primaryCat.key,
            title: primaryCat.title,
            position: primaryCat.position,
            catalogCollection: {
              items: primaryCat.linkedFrom?.catalogCollection?.items || []
            }
          }));
          setPrimaryCatalog(primaryCategories);
          
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
  }, []);

  useEffect(() => {
    fetchMediaData();
  }, [fetchMediaData]);

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
    setCatalogData([]);
    setPrimaryCatalog([]); // Mock data doesn't have structured categories
    setLoading(false);
  };

  useEffect(() => {
    fetchMediaData();
  }, [fetchMediaData]);

  // Filter & search logic
  const getFilteredData = () => {
    let filtered = mediaData;

    // Filter by primary category (应用 -> 二级分类数组 -> 一级分类)
    if (primaryCategory !== 'all') {
      filtered = filtered.filter(item => {
        // 获取应用的所有二级分类
        const secondaryCategories = item.catalogCollection?.items || [];
        if (secondaryCategories.length === 0) return false;
        
        // 检查任意二级分类是否归属于选中的一级分类
        return secondaryCategories.some(secondaryCat => {
          const primaryCat = secondaryCat.catalogCollection?.items?.[0];
          return primaryCat?.key === primaryCategory;
        });
      });
    }

    // Filter by secondary category
    if (secondaryCategory !== 'all' && primaryCategory !== 'all') {
      filtered = filtered.filter(item => {
        const secondaryCategories = item.catalogCollection?.items || [];
        return secondaryCategories.some(cat => cat.key === secondaryCategory);
      });
    }

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(item => {
        const trademark = (item.trademark || '').toLowerCase();
        const overview = (item.overview || '').toLowerCase();
        const tags = (item.tags || []).join(' ').toLowerCase();
        return trademark.includes(query) || overview.includes(query) || tags.includes(query);
      });
    }

    return filtered;
  };

  // Get data filtered by primary category only (for count display)
  const getFilteredDataByPrimaryOnly = () => {
    if (primaryCategory === 'all') return mediaData;
    
    return mediaData.filter(item => {
      const secondaryCategories = item.catalogCollection?.items || [];
      if (secondaryCategories.length === 0) return false;
      
      return secondaryCategories.some(secondaryCat => {
        const primaryCat = secondaryCat.catalogCollection?.items?.[0];
        return primaryCat?.key === primaryCategory;
      });
    });
  };

  const filteredData = getFilteredData();

  // Pagination logic
  const totalPages = Math.ceil(filteredData.length / pageSize);
  const paginatedData = filteredData.slice(
    (page - 1) * pageSize,
    page * pageSize
  );

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [primaryCategory, secondaryCategory, searchQuery, pageSize]);

  const handlePrimaryChange = (newValue) => {
    setPrimaryCategory(newValue);
    setSecondaryCategory('all');
  };

  const handleItemSelect = (item) => {
    console.log('Selected item:', item);
    // TODO: Open detail modal in future story
  };

  const isZh = locale === 'zh';
  
  return (
    <div className="App">
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            {isZh ? '应用商店' : 'Application Store'}
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
            {/* Filter Bar: Primary Category Dropdown + Search Box */}
            <FilterBar
              catalogData={primaryCatalog}
              primaryCategory={primaryCategory}
              onPrimaryChange={handlePrimaryChange}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              totalCount={mediaData.length}
              primaryCategoryCount={getFilteredDataByPrimaryOnly().length}
            />

            {/* Secondary Category Navigation (Chips) */}
            <SecondaryCategoryNav
              catalogData={primaryCatalog}
              primaryCategory={primaryCategory}
              secondaryCategory={secondaryCategory}
              onSecondaryChange={setSecondaryCategory}
              primaryCategoryCount={getFilteredDataByPrimaryOnly().length}
            />

            {/* Media Grid */}
            <MediaGrid
              items={paginatedData}
              onItemSelect={handleItemSelect}
            />

            {/* No Results */}
            {filteredData.length === 0 && (
              <Box textAlign="center" py={8}>
                <Typography variant="h6" color="text.secondary">
                  {isZh ? '未找到相关应用' : 'No applications found'}
                </Typography>
              </Box>
            )}

            {/* Pagination */}
            {filteredData.length > 0 && totalPages > 1 && (
              <PaginationControls
                page={page}
                totalPages={totalPages}
                pageSize={pageSize}
                totalItems={filteredData.length}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            )}
          </>
        )}
      </Container>
    </div>
  );
}

export default App;
