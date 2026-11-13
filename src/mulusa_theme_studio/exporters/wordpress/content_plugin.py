"""The companion plugin. A theme cannot create pages, so this creates them, once, on request.

It copies the design's images into the media library, creates each page as ordinary block
content, and points the homepage at the right one. Pages already edited are left alone.
"""
from __future__ import annotations

from .files import Identity, header_text


def plugin_php(who: Identity, nonce: str) -> str:
    prefix = who.prefix + "_content"
    slug = f"{who.slug}-content"
    return f"""<?php
/**
 * Plugin Name: {header_text(who.name)} site content
 * Description: Creates the pages designed in Mulusa Theme Studio for the {header_text(who.name)} theme, and handles its contact forms.
 * Version: {header_text(who.version)}
 * Author: {header_text(who.author) or 'Unknown'}
 * Requires at least: 6.6
 * Requires PHP: 7.4
 * License: GPLv2 or later
 * Text Domain: {slug}
 *
 * @package {slug}
 */

if ( ! defined( 'ABSPATH' ) ) {{
	exit;
}}

define( '{prefix.upper()}_NONCE', '{nonce}' );
define( '{prefix.upper()}_THEME', '{who.slug}' );

/** The exported site data. */
function {prefix}_data() {{
	static $data = null;
	if ( null === $data ) {{
		$raw  = file_get_contents( __DIR__ . '/data/site.json' ); // phpcs:ignore WordPress.WP.AlternativeFunctions
		$data = json_decode( (string) $raw, true );
		if ( ! is_array( $data ) ) {{
			$data = array( 'pages' => array(), 'forms' => array() );
		}}
	}}
	return $data;
}}

/**
 * Copies one image from the theme into the media library, once.
 *
 * @param string $file File name in the theme's assets/images folder.
 * @return int Attachment id, or 0 when the file cannot be imported.
 */
function {prefix}_import_image( $file ) {{
	$file     = sanitize_file_name( $file );
	$existing = get_posts(
		array(
			'post_type'   => 'attachment',
			'post_status' => 'inherit',
			'numberposts' => 1,
			'fields'      => 'ids',
			'meta_key'    => '_mts_source_file', // phpcs:ignore WordPress.DB.SlowDBQuery
			'meta_value'  => $file, // phpcs:ignore WordPress.DB.SlowDBQuery
		)
	);
	if ( $existing ) {{
		return (int) $existing[0];
	}}
	$source = trailingslashit( get_theme_root() ) . {prefix.upper()}_THEME . '/assets/images/' . $file;
	if ( ! is_readable( $source ) ) {{
		return 0;
	}}
	require_once ABSPATH . 'wp-admin/includes/file.php';
	require_once ABSPATH . 'wp-admin/includes/media.php';
	require_once ABSPATH . 'wp-admin/includes/image.php';
	$copy = wp_tempnam( $file );
	if ( ! copy( $source, $copy ) ) {{
		return 0;
	}}
	$id = media_handle_sideload( array( 'name' => $file, 'tmp_name' => $copy ), 0 );
	if ( is_wp_error( $id ) ) {{
		wp_delete_file( $copy );
		return 0;
	}}
	update_post_meta( $id, '_mts_source_file', $file );
	return (int) $id;
}}

/**
 * The category ids for a list of slugs, creating any that are missing.
 *
 * @param string $slugs Comma-separated slugs.
 * @return string
 */
function {prefix}_terms( $slugs ) {{
	$ids = array();
	foreach ( array_filter( explode( ',', $slugs ) ) as $slug ) {{
		$term = get_term_by( 'slug', $slug, 'category' );
		if ( ! $term ) {{
			$made = wp_insert_term( ucwords( str_replace( '-', ' ', $slug ) ), 'category', array( 'slug' => $slug ) );
			$ids[] = is_wp_error( $made ) ? 0 : (int) $made['term_id'];
		}} else {{
			$ids[] = (int) $term->term_id;
		}}
	}}
	return implode( ',', $ids );
}}

/**
 * Replaces the export's stand-ins with real ids and addresses.
 *
 * @param string $content Block markup.
 * @param array  $page_ids Design page id => WordPress page id.
 * @return string
 */
function {prefix}_resolve( $content, $page_ids ) {{
	$token = '__MTS' . {prefix.upper()}_NONCE . '_';
	// Numbers in a block's JSON lose their quotes.
	$content = preg_replace_callback(
		'/"' . $token . '(imageid|terms)_([0-9a-f]*)__"/',
		function ( $match ) {{
			$value = hex2bin( $match[2] );
			return 'imageid' === $match[1] ? (string) {prefix}_import_image( $value ) : {prefix}_terms( $value );
		}},
		$content
	);
	return preg_replace_callback(
		'/' . $token . '([a-z]+)_([0-9a-f]*)__/',
		function ( $match ) use ( $page_ids ) {{
			$value = '' === $match[2] ? '' : hex2bin( $match[2] );
			switch ( $match[1] ) {{
				case 'page':
					return isset( $page_ids[ $value ] ) ? (string) get_permalink( $page_ids[ $value ] ) : home_url( '/' );
				case 'image':
					return (string) wp_get_attachment_url( {prefix}_import_image( $value ) );
				case 'imageid':
					return (string) {prefix}_import_image( $value );
				case 'themefile':
					return trailingslashit( get_theme_root_uri() ) . {prefix.upper()}_THEME . '/' . $value;
				case 'terms':
					return {prefix}_terms( $value );
			}}
			return '';
		}},
		$content
	);
}}

/** Whoever pressed the button, or the first administrator when run from the command line. */
function {prefix}_author() {{
	$user = get_current_user_id();
	if ( $user ) {{
		return $user;
	}}
	$admins = get_users( array( 'role' => 'administrator', 'number' => 1, 'fields' => 'ID' ) );
	return $admins ? (int) $admins[0] : 0;
}}

/**
 * Creates the pages. Safe to run again: a page that already exists is reported and left alone.
 *
 * @return array[] One row for each page: design title, WordPress id, state.
 */
function {prefix}_import() {{
	$data     = {prefix}_data();
	$rows     = array();
	$page_ids = array();
	$created  = array();
	if ( get_stylesheet() !== {prefix.upper()}_THEME ) {{
		return array( array( 'title' => '', 'id' => 0, 'state' => 'theme-not-active' ) );
	}}
	if ( '' === get_option( 'permalink_structure' ) ) {{
		update_option( 'permalink_structure', '/%postname%/' );
		flush_rewrite_rules();
	}}
	foreach ( $data['pages'] as $order => $page ) {{
		$found = get_page_by_path( $page['slug'] );
		if ( $found ) {{
			$page_ids[ $page['id'] ] = (int) $found->ID;
			$rows[]                  = array( 'title' => $page['title'], 'id' => (int) $found->ID, 'state' => 'kept' );
			continue;
		}}
		$id = wp_insert_post(
			array(
				'post_type'   => 'page',
				'post_status' => 'publish',
				'post_author' => {prefix}_author(),
				'post_title'  => $page['title'],
				'post_name'   => $page['slug'],
				'menu_order'  => $order,
				'post_content' => '',
			),
			true
		);
		if ( is_wp_error( $id ) ) {{
			$rows[] = array( 'title' => $page['title'], 'id' => 0, 'state' => 'failed: ' . $id->get_error_message() );
			continue;
		}}
		update_post_meta( $id, '_mts_design_page', $page['id'] );
		if ( ! empty( $page['description'] ) ) {{
			update_post_meta( $id, '_mts_description', $page['description'] );
		}}
		if ( ! empty( $page['template'] ) ) {{
			update_post_meta( $id, '_wp_page_template', $page['template'] );
		}}
		$page_ids[ $page['id'] ] = (int) $id;
		$created[ $page['id'] ]  = $page;
		$rows[]                  = array( 'title' => $page['title'], 'id' => (int) $id, 'state' => 'created' );
	}}
	foreach ( $created as $design_id => $page ) {{
		wp_update_post(
			wp_slash(
				array(
					'ID'           => $page_ids[ $design_id ],
					'post_content' => {prefix}_resolve( $page['content'], $page_ids ),
				)
			)
		);
	}}
	if ( ! empty( $data['home'] ) && isset( $page_ids[ $data['home'] ] ) ) {{
		update_option( 'show_on_front', 'page' );
		update_option( 'page_on_front', $page_ids[ $data['home'] ] );
	}}
	if ( ! empty( $data['site_title'] ) && 'My WordPress Website' === get_option( 'blogname' ) ) {{
		update_option( 'blogname', $data['site_title'] );
	}}
	if ( ! empty( $data['logo'] ) && ! get_option( 'site_logo' ) ) {{
		$logo = {prefix}_import_image( $data['logo'] );
		if ( $logo ) {{
			update_option( 'site_logo', $logo );
			set_theme_mod( 'custom_logo', $logo );
		}}
	}}
	update_option( '{prefix}_report', $rows, false );
	return $rows;
}}

add_action( 'admin_menu', '{prefix}_menu' );
/** The import screen, under Tools. */
function {prefix}_menu() {{
	add_management_page( 'Import site content', 'Import site content', 'manage_options', '{slug}', '{prefix}_screen' );
}}

/** Shows what the import will do, or did. */
function {prefix}_screen() {{
	if ( ! current_user_can( 'manage_options' ) ) {{
		return;
	}}
	$rows = get_option( '{prefix}_report', array() );
	if ( isset( $_POST['{prefix}_run'] ) && check_admin_referer( '{prefix}_run' ) ) {{
		$rows = {prefix}_import();
	}}
	echo '<div class="wrap"><h1>' . esc_html__( 'Import site content', '{slug}' ) . '</h1>';
	echo '<p>' . esc_html__( 'This creates the pages from your design as normal WordPress pages, copies their images into the Media Library and sets the homepage. Pages that already exist are not changed.', '{slug}' ) . '</p>';
	if ( get_stylesheet() !== {prefix.upper()}_THEME ) {{
		echo '<div class="notice notice-error"><p>' . esc_html__( 'Activate the matching theme first: the images are copied from it.', '{slug}' ) . '</p></div>';
	}}
	echo '<form method="post">';
	wp_nonce_field( '{prefix}_run' );
	submit_button( esc_html__( 'Create the pages', '{slug}' ), 'primary', '{prefix}_run' );
	echo '</form>';
	if ( $rows ) {{
		echo '<h2>' . esc_html__( 'Pages', '{slug}' ) . '</h2><table class="widefat striped"><thead><tr><th>' . esc_html__( 'Page in your design', '{slug}' ) . '</th><th>' . esc_html__( 'WordPress page', '{slug}' ) . '</th><th>' . esc_html__( 'Result', '{slug}' ) . '</th></tr></thead><tbody>';
		foreach ( $rows as $row ) {{
			$link = $row['id'] ? '<a href="' . esc_url( (string) get_edit_post_link( $row['id'] ) ) . '">' . esc_html( get_the_title( $row['id'] ) ) . '</a>' : '';
			echo '<tr><td>' . esc_html( $row['title'] ) . '</td><td>' . wp_kses_post( $link ) . '</td><td>' . esc_html( $row['state'] ) . '</td></tr>';
		}}
		echo '</tbody></table>';
	}}
	echo '</div>';
}}

add_action( 'wp_head', '{prefix}_description' );
/** The page description set in the design. */
function {prefix}_description() {{
	if ( is_singular( 'page' ) ) {{
		$text = get_post_meta( get_the_ID(), '_mts_description', true );
		if ( $text ) {{
			echo '<meta name="description" content="' . esc_attr( $text ) . '">' . "\\n";
		}}
	}}
}}

add_shortcode( 'mulusa_form', '{prefix}_form' );
/**
 * A contact form from the design.
 *
 * @param array $atts Shortcode attributes.
 * @return string
 */
function {prefix}_form( $atts ) {{
	$atts = shortcode_atts( array( 'id' => '' ), $atts );
	$data = {prefix}_data();
	$form = isset( $data['forms'][ $atts['id'] ] ) ? $data['forms'][ $atts['id'] ] : null;
	if ( ! $form ) {{
		return '';
	}}
	$note = '';
	// phpcs:ignore WordPress.Security.NonceVerification.Recommended
	if ( isset( $_GET['mts_form'] ) ) {{
		$note = 'sent' === $_GET['mts_form'] ? __( 'Thank you. Your message has been sent.', '{slug}' ) : __( 'Sorry, your message could not be sent.', '{slug}' ); // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		$note = '<p class="mts-form-note" role="status">' . esc_html( $note ) . '</p>';
	}}
	$html = $note . '<form class="mts-form ' . esc_attr( $form['class'] ) . '" action="' . esc_url( admin_url( 'admin-post.php' ) ) . '" method="post">';
	$html .= '<input type="hidden" name="action" value="{prefix}_send"><input type="hidden" name="form" value="' . esc_attr( $atts['id'] ) . '">';
	$html .= wp_nonce_field( '{prefix}_send', '_wpnonce', true, false );
	$html .= '<p style="position:absolute;left:-9999px" aria-hidden="true"><label>Leave empty<input type="text" name="website" tabindex="-1" autocomplete="off"></label></p>';
	foreach ( $form['fields'] as $index => $field ) {{
		$name  = 'field_' . (int) $index;
		$html .= '<label class="mts-field">' . esc_html( $field['label'] );
		if ( 'textarea' === $field['type'] ) {{
			$html .= '<textarea name="' . esc_attr( $name ) . '" rows="5"></textarea>';
		}} else {{
			$html .= '<input type="' . esc_attr( $field['type'] ) . '" name="' . esc_attr( $name ) . '">';
		}}
		$html .= '</label>';
	}}
	$html .= '<div class="wp-block-button mts-wp-btn mts-wp-btn-primary"><button class="wp-block-button__link wp-element-button" type="submit">' . esc_html( $form['submit'] ) . '</button></div></form>';
	return $html;
}}

add_action( 'admin_post_{prefix}_send', '{prefix}_send' );
add_action( 'admin_post_nopriv_{prefix}_send', '{prefix}_send' );
/** Emails a form's contents to the site's administrator. */
function {prefix}_send() {{
	check_admin_referer( '{prefix}_send' );
	$back = wp_get_referer() ? wp_get_referer() : home_url( '/' );
	$data = {prefix}_data();
	$id   = isset( $_POST['form'] ) ? sanitize_key( wp_unslash( $_POST['form'] ) ) : '';
	$form = isset( $data['forms'][ $id ] ) ? $data['forms'][ $id ] : null;
	if ( ! $form || ! empty( $_POST['website'] ) ) {{
		wp_safe_redirect( add_query_arg( 'mts_form', 'failed', $back ) );
		exit;
	}}
	$lines = array();
	foreach ( $form['fields'] as $index => $field ) {{
		$key     = 'field_' . (int) $index;
		$value   = isset( $_POST[ $key ] ) ? sanitize_textarea_field( wp_unslash( $_POST[ $key ] ) ) : '';
		$lines[] = $field['label'] . ': ' . $value;
	}}
	$sent = wp_mail( get_option( 'admin_email' ), sprintf( '[%s] Website message', get_bloginfo( 'name' ) ), implode( "\\n", $lines ) );
	wp_safe_redirect( add_query_arg( 'mts_form', $sent ? 'sent' : 'failed', $back ) );
	exit;
}}

if ( defined( 'WP_CLI' ) && WP_CLI ) {{
	WP_CLI::add_command(
		'mulusa-content import',
		function () {{
			foreach ( {prefix}_import() as $row ) {{
				WP_CLI::log( $row['title'] . ' -> ' . $row['id'] . ' (' . $row['state'] . ')' );
			}}
		}}
	);
}}
"""
