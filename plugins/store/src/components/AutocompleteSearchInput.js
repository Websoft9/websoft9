import React, { useState, useEffect, useRef } from 'react';
import { SearchInput } from '@patternfly/react-core';
import { 
  debounce, 
  getSuggestions, 
  getSearchHistory, 
  addSearchHistory,
  DEBOUNCE_MS 
} from '../utils/searchUtils';
import './AutocompleteSearchInput.css';

/**
 * Autocomplete search input component
 * - Shows dropdown suggestions as user types
 * - Supports keyboard navigation (↑↓ Enter ESC)
 * - Displays app icon, name, and category
 * - Shows search history when empty
 */
const AutocompleteSearchInput = ({ 
  searchIndex, 
  value, 
  onChange, 
  onSelect,
  placeholder 
}) => {
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);
  
  // Debounced suggestion fetch
  const debouncedFetch = useRef(
    debounce((query, index) => {
      const history = getSearchHistory();
      const results = getSuggestions(query, index, history);
      setSuggestions(results);
      setShowDropdown(results.length > 0);
      setSelectedIndex(-1);
    }, DEBOUNCE_MS)
  ).current;
  
  // Handle input change
  const handleInputChange = (_event, newValue) => {
    onChange(_event, newValue);
    debouncedFetch(newValue, searchIndex);
  };
  
  // Handle keyboard navigation
  const handleKeyDown = (e) => {
    if (!showDropdown) return;
    
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, -1));
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault();
      handleSelect(suggestions[selectedIndex]);
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
      setSelectedIndex(-1);
    }
  };
  
  // Handle suggestion selection
  const handleSelect = (item) => {
    const selectedText = item.text || item.name;
    onChange(null, selectedText);
    addSearchHistory(selectedText);
    if (onSelect) onSelect(selectedText);
    setShowDropdown(false);
    setSelectedIndex(-1);
  };
  
  // Handle clear
  const handleClear = () => {
    onChange(null, '');
    setShowDropdown(false);
    setSuggestions([]);
    setSelectedIndex(-1);
  };
  
  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  return (
    <div className="autocomplete-search-wrapper" ref={dropdownRef}>
      <SearchInput
        ref={inputRef}
        placeholder={placeholder}
        value={value}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        onClear={handleClear}
      />
      {showDropdown && (
        <SuggestionDropdown 
          suggestions={suggestions}
          selectedIndex={selectedIndex}
          onSelect={handleSelect}
        />
      )}
    </div>
  );
};

/**
 * Suggestion dropdown list
 */
const SuggestionDropdown = ({ suggestions, selectedIndex, onSelect }) => {
  return (
    <div className="autocomplete-dropdown">
      {suggestions.map((item, index) => (
        <SuggestionItem 
          key={item.key || item.text || index}
          item={item}
          isSelected={index === selectedIndex}
          onClick={() => onSelect(item)}
        />
      ))}
    </div>
  );
};

/**
 * Individual suggestion item
 */
const SuggestionItem = ({ item, isSelected, onClick }) => {
  const isHistory = item.type === 'history';
  
  return (
    <div 
      className={`autocomplete-item ${isSelected ? 'selected' : ''}`}
      onClick={onClick}
      role="option"
      aria-selected={isSelected}
    >
      {isHistory ? (
        <>
          <span className="autocomplete-icon history-icon">🕐</span>
          <span className="autocomplete-name">{item.text}</span>
        </>
      ) : (
        <>
          {item.logo && (
            <img 
              src={item.logo} 
              alt="" 
              className="autocomplete-icon app-logo"
            />
          )}
          <span className="autocomplete-name">{item.name}</span>
          {item.category && (
            <span className="autocomplete-category">{item.category}</span>
          )}
        </>
      )}
    </div>
  );
};

export default AutocompleteSearchInput;
