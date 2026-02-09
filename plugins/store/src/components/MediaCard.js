import React from 'react';
import {
  Card,
  CardBody,
  CardTitle,
  Label
} from '@patternfly/react-core';
import { t } from '../i18n';
import './MediaCard.css';

/**
 * MediaCard Component - PatternFly version
 * Displays application card with logo, name, description, and category
 * Features: native lazy loading, error fallback
 */
const MediaCard = ({ item, onSelect }) => {
  const handleError = (e) => {
    e.target.src = '/placeholder.png';
  };

  // Extract data from item structure
  const logoUrl = item.logo?.imageurl || item.logo || '/placeholder.png';
  const displayName = item.trademark || item.name || t('store.card.unknownApp');
  const summary = item.summary || item.overview || t('store.card.noDescription');
  const category = item.catalogCollection?.items?.[0]?.title || item.category || t('store.card.defaultCategory');
  const tags = item.tags || [];

  return (
    <Card 
      isClickable
      isSelectable
      onClick={() => onSelect && onSelect(item.key)}
      className="media-card"
    >
      <CardBody>
        {/* Logo Container */}
        <div className="media-card-logo">
          <img 
            src={logoUrl}
            alt={displayName}
            onError={handleError}
            loading="lazy"
          />
        </div>

        {/* Card Title */}
        <CardTitle className="media-card-title">
          {displayName}
        </CardTitle>

        {/* Summary */}
        <div className="media-card-description">
          {summary}
        </div>

        {/* Categories and Tags */}
        <div className="media-card-labels">
          <Label color="blue">{category}</Label>
          {tags && tags.slice(0, 2).map((tag, index) => (
            <Label key={index} color="grey">{tag}</Label>
          ))}
        </div>
      </CardBody>
    </Card>
  );
};

export default MediaCard;
