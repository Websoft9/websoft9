<?php
/**
 * Defines constants and global variables that can be overridden, generally in wp-config.php.
 *
 * @package WordPress
 */


/**
 * Defines templating-related WordPress constants.
 *
 * @since 3.0.0
 */
function wp_templating_constants() {
	/**
	 * Filesystem path to the current active template directory.
	 *
	 * @since 1.5.0
	 */
	define( 'TEMPLATEPATH', get_template_directory() );

	/**
	 * Filesystem path to the current active template stylesheet directory.
	 *
	 * @since 2.1.0
	 */
	define( 'STYLESHEETPATH', get_stylesheet_directory() );

	/**
	 * Slug of the default theme for this installation.
	 * Used as the default theme when installing new sites.
	 * It will be used as the fallback if the active theme doesn't exist.
	 *
	 * @since 3.0.0
	 *
	 * @see WP_Theme::get_core_default_theme()
	 */
	if ( ! defined( 'WP_DEFAULT_THEME' ) ) {
		define( 'WP_DEFAULT_THEME', '{{wordpress_solution}}' );
	}
}
