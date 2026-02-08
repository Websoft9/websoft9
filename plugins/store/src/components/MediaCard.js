import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardMedia,
  Typography,
  CardActionArea,
  Chip,
  Box
} from '@mui/material';
import LazyLoad from 'react-lazyload';
import './MediaCard.css';

/**
 * MediaCard Component - Extracted from appstore.js AppImage pattern
 * Displays application card with logo, name, description, and category
 * Features: skeleton loading, lazy loading, error fallback
 */
const MediaCard = ({ item, onSelect, isFirstScreen = false }) => {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  const handleLoad = () => {
    setLoaded(true);
  };

  const handleError = (e) => {
    setError(true);
    e.target.src = '/placeholder.png';
  };

  // Extract data from item structure (compatible with both formats)
  const logoUrl = item.logo?.imageurl || item.logo || '/placeholder.png';
  const displayName = item.trademark || item.name || 'Unknown App';
  const description = item.overview || item.description || 'No description available';
  const category = item.catalogCollection?.items?.[0]?.title || item.category || 'General';
  const tags = item.tags || [];

  const cardContent = (
    <Card 
      sx={{ 
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.3s ease',
        '&:hover': {
          transform: 'translateY(-8px)',
          boxShadow: 6
        }
      }}
    >
      <CardActionArea onClick={() => onSelect && onSelect(item)}>
        {/* Image Container with Skeleton */}
        <Box sx={{ position: 'relative', height: 160, backgroundColor: '#fafafa' }}>
          {/* Skeleton Screen */}
          {!loaded && !error && (
            <Box
              className="skeleton-container"
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                opacity: loaded ? 0 : 1,
                transition: 'opacity 0.3s ease',
                zIndex: 1
              }}
            >
              <Box
                className="skeleton-box"
                sx={{
                  width: 80,
                  height: 80,
                  backgroundColor: '#e0e0e0',
                  borderRadius: '8px'
                }}
              />
            </Box>
          )}

          {/* Actual Image */}
          <CardMedia
            component="img"
            height="160"
            image={logoUrl}
            alt={displayName}
            onLoad={handleLoad}
            onError={handleError}
            loading={isFirstScreen ? 'eager' : 'lazy'}
            sx={{ 
              objectFit: 'contain', 
              p: 3, 
              backgroundColor: '#fafafa',
              borderBottom: '1px solid #e0e0e0',
              opacity: loaded || error ? 1 : 0,
              transition: 'opacity 0.3s ease',
              position: 'relative',
              zIndex: 2
            }}
          />
        </Box>

        <CardContent sx={{ flexGrow: 1 }}>
          <Typography 
            gutterBottom 
            variant="h6" 
            component="div"
            sx={{ 
              fontWeight: 600,
              fontSize: '1.1rem',
              mb: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          >
            {displayName}
          </Typography>
          
          <Typography 
            variant="body2" 
            color="text.secondary"
            sx={{ 
              mb: 2,
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              minHeight: '40px',
              lineHeight: 1.5
            }}
          >
            {description}
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Chip 
              label={category} 
              size="small" 
              color="primary"
              variant="outlined"
            />
            {tags && tags.slice(0, 2).map((tag, index) => (
              <Chip 
                key={index}
                label={tag} 
                size="small" 
                variant="outlined"
              />
            ))}
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );

  // Wrap in LazyLoad for off-screen items (performance optimization)
  if (isFirstScreen) {
    return cardContent;
  }

  return (
    <LazyLoad height={300} offset={300} once>
      {cardContent}
    </LazyLoad>
  );
};

export default MediaCard;
