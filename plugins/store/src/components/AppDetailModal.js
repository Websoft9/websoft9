import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalVariant,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Label,
  Spinner,
  Alert,
  Title,
  Content,
  ContentVariants,
  Flex,
  FlexItem
} from '@patternfly/react-core';
import {
  GithubIcon,
  GlobeIcon,
  AngleLeftIcon,
  AngleRightIcon,
  StarIcon as StarFilledIcon,
  OutlinedStarIcon,
  DownloadIcon
} from '@patternfly/react-icons';
import ReactMarkdown from 'react-markdown';
import { t, getCurrentLocale } from '../i18n';
import './AppDetailModal.css';

/**
 * AppDetailModal Component - Story 5.6
 * Display-only application detail modal (no installation functionality)
 * Shows comprehensive information about an application when user clicks on card
 */
const AppDetailModal = ({ 
  open, 
  onClose, 
  product, 
  loading, 
  error,
  onCategoryClick,  // Callback when category is clicked
  onInstall,        // Callback for install action (future)
  onFavorite,       // Callback for favorite action (future)
  isFavorite = false // Whether this app is favorited (future)
}) => {
  const [activeStep, setActiveStep] = useState(0);
  
  // Reset active step when product changes or modal closes
  useEffect(() => {
    if (!open) {
      setActiveStep(0);
    }
  }, [open, product?.key]);
  
  if (!product && !loading && !error) return null;

  // Get screenshots array
  const screenshots = product?.screenshots || [];
  const maxSteps = screenshots.length;

  // Screenshot navigation handlers
  const handleNext = () => {
    setActiveStep((prevStep) => Math.min(prevStep + 1, maxSteps - 1));
  };

  const handleBack = () => {
    setActiveStep((prevStep) => Math.max(prevStep - 1, 0));
  };

  // Handle category click - close modal and navigate to category
  const handleCategoryClick = (category) => {
    if (onCategoryClick) {
      onClose();
      onCategoryClick(category);
    }
  };

  // Construct documentation URL based on current locale
  const getDocUrl = (key) => {
    const locale = getCurrentLocale();
    const path = locale === 'zh' ? `docs/${key}` : `en/docs/${key}`;
    return `https://support.websoft9.com/${path}`;
  };

  // Construct GitHub URL
  const getGithubUrl = (key) => {
    return `https://github.com/Websoft9/docker-library/tree/main/apps/${key}`;
  };

  // Construct screenshot URL
  const getScreenshotUrl = (item) => {
    const locale = getCurrentLocale();
    const filename = item.value ? item.value.split('/').pop() : '';
    return `/w9media/screenshots/${locale}/${filename}`;
  };

  return (
    <Modal
      variant={ModalVariant.large}
      isOpen={open}
      onClose={onClose}
      aria-labelledby="app-detail-modal-title"
      aria-describedby="app-detail-modal-description"
    >
      {loading && (
        <ModalBody>
          <div className="app-detail-loading">
            <Spinner size="lg" />
            <Content component={ContentVariants.p}>{t('modal.loading')}</Content>
          </div>
        </ModalBody>
      )}

      {error && (
        <ModalBody>
          <Alert variant="danger" title={t('modal.error')} />
        </ModalBody>
      )}

      {product && !loading && !error && (
        <>
          <ModalHeader title={product.trademark} />
          <ModalBody>
          <Flex className="app-detail-header" alignItems={{ default: 'alignItemsFlexStart' }} spaceItems={{ default: 'spaceItemsMd' }}>
            {/* App Icon */}
            <FlexItem>
              <img
                src={product.logo?.imageurl || `/media/logos/${product.logo}` || '/placeholder.png'}
                alt={product.trademark}
                className="app-detail-icon"
                onError={(e) => {
                  e.target.src = '/placeholder.png';
                }}
              />
            </FlexItem>

            {/* App Metadata */}
            <FlexItem flex={{ default: 'flex_1' }}>
              {/* Links Row */}
              <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsSm' }} flexWrap={{ default: 'wrap' }}>
                <FlexItem>
                  <a
                    href={getDocUrl(product.key)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="app-detail-link"
                  >
                    <Label color="blue">{t('modal.documentation')}</Label>
                  </a>
                </FlexItem>
                {/* GitHub Link */}
                <FlexItem>
                  <a
                    href={getGithubUrl(product.key)}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="GitHub Repository"
                    className="app-detail-icon-link"
                  >
                    <GithubIcon />
                  </a>
                </FlexItem>
                {/* Website Link */}
                {product.websiteurl && (
                  <FlexItem>
                    <a
                      href={product.websiteurl}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={t('modal.website')}
                      className="app-detail-icon-link"
                    >
                      <GlobeIcon />
                    </a>
                  </FlexItem>
                )}
              </Flex>

              {/* Version */}
              {product.version && (
                <div className="app-detail-metadata">
                  <Content component={ContentVariants.small}>
                    <strong>{t('modal.version')}:</strong> {Array.isArray(product.version) ? product.version.join(', ') : product.version}
                  </Content>
                </div>
              )}

              {/* System Requirements */}
              {(product.vcpu || product.memory || product.storage) && (
                <div className="app-detail-metadata">
                  <Content component={ContentVariants.small}>
                    <strong>{t('modal.requires')}:</strong> {product.vcpu || 1} vCPU, {product.memory || 2} GB memory, {product.storage || 8} GB storage
                  </Content>
                </div>
              )}

              {/* Categories */}
              {product.catalogCollection?.items && product.catalogCollection.items.length > 0 && (
                <Flex alignItems={{ default: 'alignItemsCenter' }} spaceItems={{ default: 'spaceItemsXs' }} flexWrap={{ default: 'wrap' }}>
                  <FlexItem>
                    <Content component={ContentVariants.small}>
                      <strong>{t('modal.categories')}:</strong>
                    </Content>
                  </FlexItem>
                  {product.catalogCollection.items.map((category, index) => (
                    <React.Fragment key={category.key || index}>
                      <FlexItem>
                        <span
                          className="app-detail-category-link"
                          onClick={() => handleCategoryClick(category)}
                        >
                          {category.title}
                        </span>
                      </FlexItem>
                      {index < product.catalogCollection.items.length - 1 && (
                        <FlexItem>
                          <Content component={ContentVariants.small}>|</Content>
                        </FlexItem>
                      )}
                    </React.Fragment>
                  ))}
                </Flex>
              )}
            </FlexItem>
          </Flex>

          {/* Modal Body */}
          <div className="app-detail-body">
            {/* Screenshots Carousel */}
            {screenshots.length > 0 && (
              <div className="app-detail-carousel">
                <div className="carousel-wrapper">
                  {/* Left Arrow */}
                  {maxSteps > 1 && (
                    <Button
                      variant="plain"
                      onClick={handleBack}
                      isDisabled={activeStep === 0}
                      className="carousel-button carousel-button-left"
                      aria-label="Previous screenshot"
                    >
                      <AngleLeftIcon />
                    </Button>
                  )}

                  {/* Screenshot Image */}
                  <img
                    className="carousel-image"
                    src={getScreenshotUrl(screenshots[activeStep])}
                    alt={`Screenshot ${activeStep + 1}`}
                    onError={(e) => {
                      e.target.src = '/placeholder.png';
                    }}
                  />

                  {/* Right Arrow */}
                  {maxSteps > 1 && (
                    <Button
                      variant="plain"
                      onClick={handleNext}
                      isDisabled={activeStep === maxSteps - 1}
                      className="carousel-button carousel-button-right"
                      aria-label="Next screenshot"
                    >
                      <AngleRightIcon />
                    </Button>
                  )}
                </div>

                {/* Dots indicator */}
                {maxSteps > 1 && (
                  <div className="carousel-dots">
                    {screenshots.map((_, index) => (
                      <span
                        key={index}
                        className={`carousel-dot ${index === activeStep ? 'active' : ''}`}
                        onClick={() => setActiveStep(index)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Overview Section */}
            {product.overview && (
              <div className="app-detail-section">
                <Title headingLevel="h3" size="lg">
                  {t('modal.overview')}
                </Title>
                <Content component={ContentVariants.p}>
                  {product.overview}
                </Content>
              </div>
            )}

            {/* Description Section (supports Markdown) */}
            {product.description && (
              <div className="app-detail-section">
                <Title headingLevel="h3" size="lg">
                  {t('modal.description')}
                </Title>
                <div className="markdown-content">
                  <ReactMarkdown>{product.description}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
          </ModalBody>
          <ModalFooter>
            <Button
              variant="primary"
              onClick={() => onInstall && onInstall(product)}
            >
              <DownloadIcon />
              {' '}{t('modal.install')}
            </Button>
            <Button
              variant="secondary"
              onClick={() => onFavorite && onFavorite(product)}
            >
              {isFavorite ? <StarFilledIcon /> : <OutlinedStarIcon />}
              {' '}{t('modal.favorite')}
            </Button>
            <Button variant="link" onClick={onClose}>
              {t('modal.close')}
            </Button>
          </ModalFooter>
        </>
      )}
    </Modal>
  );
};

export default AppDetailModal;
