import html
import os
import re
from pathlib import Path

from modules.helpers import strip_nonalphanum


class HTTPTableObject(object):

    """docstring for HTTPTableObject"""

    def __init__(self):
        super(HTTPTableObject, self).__init__()
        self._id = None
        self._screenshot_path = None
        self._http_headers = {}
        self._page_title = None
        self._remote_system = None
        self._remote_login = None
        self._source_path = None
        self._error_state = None
        self._blank = False
        self._uadata = []
        self._source_code = None
        self._max_difference = None
        self._root_path = None
        self._default_creds = None
        self._category = None
        self._ssl_error = False
        self._ua_left = None
        self._resolved = None
        # AI-powered credential detection fields
        self._ai_application_info = None  # Dict with app name, version, type
        self._ai_credentials_found = None  # List of credentials found via AI
        self._auth_info = None  # Dict with login form details
        self._credential_test_result = None  # CredentialTestResult dict
        self._auth_method_stored = None  # Stored auth method for password spraying
        # Enhanced report data
        self._technologies = None  # List of detected technologies
        self._ssl_info = None  # Dict with SSL/TLS certificate info
        self._network_logs = None  # List of network requests
        self._console_logs = None  # List of console logs
        self._cookies = None  # List of cookies
        self._response_size = None  # Size of response in bytes
        self._load_time = None  # Page load time in seconds
        self._http_auth_type = None  # HTTP authentication type (Basic, NTLM, Digest, etc.)

    def set_paths(self, outdir, suffix=None):
        file_name = self.remote_system.replace('://', '.')
        for char in [':', '/', '?', '=', '%', '+']:
            file_name = file_name.replace(char, '.')
        self.root_path = outdir
        if suffix is not None:
            file_name += '_' + suffix
        
        # Use pathlib for cross-platform path handling
        output_path = Path(outdir)
        self.screenshot_path = str(output_path / 'screens' / f'{file_name}.png')
        self.source_path = str(output_path / 'source' / f'{file_name}.txt')

    @property
    def resolved(self):
        return self._resolved

    @resolved.setter
    def resolved(self, resolved):
        self._resolved = resolved

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, id):
        self._id = id

    @property
    def ua_left(self):
        return self._ua_left

    @ua_left.setter
    def ua_left(self, ua_left):
        self._ua_left = ua_left

    @property
    def root_path(self):
        return self._root_path

    @root_path.setter
    def root_path(self, root_path):
        self._root_path = root_path

    @property
    def screenshot_path(self):
        return self._screenshot_path

    @screenshot_path.setter
    def screenshot_path(self, screenshot_path):
        self._screenshot_path = screenshot_path

    @property
    def http_headers(self):
        return self._http_headers

    @http_headers.setter
    def http_headers(self, headers):
        self._http_headers = headers

    @property
    def page_title(self):
        return self._page_title

    @page_title.setter
    def page_title(self, page_title):
        self._page_title = page_title

    @property
    def remote_system(self):
        return self._remote_system

    @remote_system.setter
    def remote_system(self, remote_system):
        if remote_system.startswith('http://') or remote_system.startswith('https://'):
            pass
        else:
            if ':8443' in remote_system or ':443' in remote_system:
                remote_system = 'https://' + remote_system
            else:
                remote_system = 'http://' + remote_system

        remote_system = remote_system.strip()
        if 'http://' in remote_system and re.search(':80$', remote_system) is not None:
            remote_system = remote_system.replace(':80', '')

        if 'https://' in remote_system and re.search(':443$', remote_system) is not None:
            remote_system = remote_system.replace(':443', '')

        self._remote_system = remote_system.strip()

    @property
    def source_path(self):
        return self._source_path

    @source_path.setter
    def source_path(self, source_path):
        self._source_path = source_path

    @property
    def headers(self):
        """
        Display headers for report generation
        
        Uses collected headers if available, otherwise falls back to 
        the original "Missing Headers" message for backward compatibility
        """
        # First check if we have explicitly set display headers
        if hasattr(self, '_headers') and self._headers:
            return self._headers
        # Then check if we have raw HTTP headers collected
        elif hasattr(self, '_http_headers') and self._http_headers:
            # Return formatted version of raw headers for display
            formatted = {}
            for key, value in self._http_headers.items():
                # Truncate very long header values for display
                display_value = value[:150] + "..." if len(value) > 150 else value
                formatted[key] = display_value
            return formatted
        else:
            # Fallback to original behavior for backward compatibility
            return {"Missing Headers": "No Headers found"}

    @headers.setter  
    def headers(self, headers):
        """Set display headers (can include security analysis)"""
        self._headers = headers

    @property
    def error_state(self):
        return self._error_state

    # Error states include Timeouts and other errors
    @error_state.setter
    def error_state(self, error_state):
        self._error_state = error_state

    @property
    def blank(self):
        return self._blank

    @blank.setter
    def blank(self, blank):
        self._blank = blank

    @property
    def source_code(self):
        return self._source_code

    @source_code.setter
    def source_code(self, source_code):
        self._source_code = source_code

    @property
    def max_difference(self):
        return self._max_difference

    @max_difference.setter
    def max_difference(self, max_difference):
        self._max_difference = max_difference

    @property
    def default_creds(self):
        return self._default_creds

    @default_creds.setter
    def default_creds(self, default_creds):
        self._default_creds = default_creds

    @property
    def category(self):
        return self._category

    @category.setter
    def category(self, category):
        self._category = category

    @property
    def ssl_error(self):
        return self._ssl_error

    @ssl_error.setter
    def ssl_error(self, ssl_error):
        self._ssl_error = ssl_error

    @property
    def ai_application_info(self):
        return self._ai_application_info

    @ai_application_info.setter
    def ai_application_info(self, ai_application_info):
        self._ai_application_info = ai_application_info

    @property
    def ai_credentials_found(self):
        return self._ai_credentials_found

    @ai_credentials_found.setter
    def ai_credentials_found(self, ai_credentials_found):
        self._ai_credentials_found = ai_credentials_found

    @property
    def auth_info(self):
        return self._auth_info

    @auth_info.setter
    def auth_info(self, auth_info):
        self._auth_info = auth_info

    @property
    def credential_test_result(self):
        return self._credential_test_result

    @credential_test_result.setter
    def credential_test_result(self, credential_test_result):
        self._credential_test_result = credential_test_result

    @property
    def auth_method_stored(self):
        return self._auth_method_stored

    @auth_method_stored.setter
    def auth_method_stored(self, auth_method_stored):
        self._auth_method_stored = auth_method_stored

    @property
    def technologies(self):
        return self._technologies

    @technologies.setter
    def technologies(self, technologies):
        self._technologies = technologies

    @property
    def ssl_info(self):
        return self._ssl_info

    @ssl_info.setter
    def ssl_info(self, ssl_info):
        self._ssl_info = ssl_info

    @property
    def network_logs(self):
        return self._network_logs

    @network_logs.setter
    def network_logs(self, network_logs):
        self._network_logs = network_logs

    @property
    def console_logs(self):
        return self._console_logs

    @console_logs.setter
    def console_logs(self, console_logs):
        self._console_logs = console_logs

    @property
    def cookies(self):
        return self._cookies

    @cookies.setter
    def cookies(self, cookies):
        self._cookies = cookies

    @property
    def response_size(self):
        return self._response_size

    @response_size.setter
    def response_size(self, response_size):
        self._response_size = response_size

    @property
    def load_time(self):
        return self._load_time

    @load_time.setter
    def load_time(self, load_time):
        self._load_time = load_time

    @property
    def http_auth_type(self):
        return self._http_auth_type

    @http_auth_type.setter
    def http_auth_type(self, http_auth_type):
        self._http_auth_type = http_auth_type

    def create_table_html(self):
        scr_path = os.path.relpath(self.screenshot_path, self.root_path)
        src_path = os.path.relpath(self.source_path, self.root_path)
        html = u""
        if self._remote_login is not None:
            html += ("""<tr>
            <td><div style=\"display: inline-block; width: 300px; word-wrap: break-word\">
            <a href=\"{address}\" target=\"_blank\">{address}</a><br>
            """).format(address=self._remote_login)
        else:
            html += ("""<tr>
            <td><div style=\"display: inline-block; width: 300px; word-wrap: break-word\">
            <a href=\"{address}\" target=\"_blank\">{address}</a><br>
            """).format(address=self.remote_system)

        if self.resolved != None and self.resolved != 'Unknown':
            html += ("""<b>Resolved to:</b> {0}<br>""").format(self.resolved)

        if len(self._uadata) > 0:
            html += ("""
                <br><b>This is the baseline request.</b><br>
                The browser type is: <b>Baseline</b><br><br>
                The user agent is: <b>Baseline</b><br><br>""")

        if self.ssl_error:
            html += "<br><b>SSL Certificate error present on\
                     <a href=\"{0}\" target=\"_blank\">{0}</a></b><br>".format(
                self.remote_system)

        # Show HTTP authentication type if detected (NTLM, Basic, etc.)
        if hasattr(self, '_http_auth_type') and self._http_auth_type:
            html += "<br><b style='color: #e67e22;'>⚠️ HTTP Authentication:</b> {0}<br>".format(
                self.sanitize(self._http_auth_type))
            html += "<small style='color: #666;'>This site requires browser-level authentication (popup)</small><br>"

        if self.default_creds is not None:
            try:
                html += "<br><b>Default credentials:</b> {0}<br>".format(
                    self.sanitize(self.default_creds))
            except UnicodeEncodeError:
                html += u"<br><b>Default credentials:</b> {0}<br>".format(
                    self.sanitize(self.default_creds))
        
        # AI-detected application info
        if self.ai_application_info:
            app_name = self.ai_application_info.get('application_name')
            if app_name:
                try:
                    html += "<br><b>AI-Detected Application:</b> {0}".format(
                        self.sanitize(app_name))
                    version = self.ai_application_info.get('version')
                    if version:
                        html += " (Version: {0})".format(self.sanitize(version))
                    html += "<br>"
                except (UnicodeEncodeError, AttributeError):
                    pass
        
        # AI-found credentials
        if self.ai_credentials_found:
            try:
                html += "<br><b>AI-Found Credentials:</b><br>"
                for cred in self.ai_credentials_found:
                    username = cred.get('username', 'N/A')
                    password = cred.get('password', 'N/A')
                    html += "  - {0}:{1}<br>".format(
                        self.sanitize(str(username)),
                        self.sanitize(str(password)))
            except (UnicodeEncodeError, AttributeError):
                pass
        
        # Credential test results
        if self.credential_test_result:
            try:
                result = self.credential_test_result
                html += "<br><b>Credential Testing:</b><br>"
                
                if result.get('testable'):
                    html += "  - Testable: Yes<br>"
                    if result.get('tested'):
                        html += "  - Tested: Yes<br>"
                        html += "  - Credentials Tested: {0}<br>".format(
                            result.get('credentials_tested', 0))
                        html += "  - Successful: {0}<br>".format(
                            result.get('successful_count', 0))
                        html += "  - Failed: {0}<br>".format(
                            result.get('failed_count', 0))
                        
                        # Show successful credentials
                        successful = result.get('successful_credentials', [])
                        if successful:
                            html += "  <b>Working Credentials:</b><br>"
                            for cred in successful:
                                html += "    - {0}:{1}<br>".format(
                                    self.sanitize(str(cred.get('username', ''))),
                                    self.sanitize(str(cred.get('password', ''))))
                    else:
                        html += "  - Tested: No<br>"
                else:
                    html += "  - Testable: No<br>"
                    errors = result.get('errors', [])
                    if errors:
                        html += "  - Errors: {0}<br>".format(
                            self.sanitize('; '.join(errors[:3])))  # Show first 3 errors
            except (UnicodeEncodeError, AttributeError, KeyError) as e:
                pass

        if self.error_state is None:
            try:
                html += "\n<br><b> Page Title: </b>{0}\n".format(
                    self.sanitize(self.page_title))
            except AttributeError:
                html += "\n<br><b> Page Title:</b>{0}\n".format(
                    'Unable to Display')
            except UnicodeDecodeError:
                html += "\n<br><b> Page Title:</b>{0}\n".format(
                    'Unable to Display')
            except UnicodeEncodeError:
                html += u"\n<br><b> Page Title:</b>{0}\n".format(
                    self.sanitize(self.page_title))

            for key, value in self.headers.items():
                try:
                    # Regular header display
                    html += '<br><b> {0}:</b> {1}\n'.format(
                        self.sanitize(key), self.sanitize(value))
                except UnicodeEncodeError:
                    html += u'<br><b> {0}:</b> {1}\n'.format(
                        self.sanitize(key), self.sanitize(value))
        if self.blank:
            html += ("""<br></td>
            <td><div style=\"display: inline-block; width: 850px;\">Page Blank\
            ,Connection error, or SSL Issues</div></td>
            </tr>
            """)
        elif self.error_state == 'Timeout':
            html += ("</td><td>Hit timeout limit")
            if os.path.isfile(self.screenshot_path):
                html += ("""<br>
                <div id=\"screenshot\"><a href=\"{1}\"
                target=\"_blank\"><img style=\"max-height:400px;height: expression(this.height > 400 ? 400: true);\"
                src=\"{1}\"></a></div></td></tr>""").format(src_path, scr_path)
            else:
                html += ("</td></tr>")
        elif self.error_state == 'BadStatus':
            html += ("""</td><td>Unknown error while attempting to
            screenshot</td></tr>""")
        elif self.error_state == 'ConnReset':
            html += ("""</td><td>Connection Reset</td></tr>""")
        elif self.error_state == 'ConnRefuse':
            html += ("""</td><td>Connection Refused</td></tr>""")
        elif self.error_state == 'SSLHandshake':
            html += ("""</td><td>SSL Handshake Error</td></tr>""")
        else:
            html += ("""<br><br><a href=\"{0}\"
                target=\"_blank\">Source Code</a></div></td>
                <td><div id=\"screenshot\"><a href=\"{1}\"
                target=\"_blank\"><img style=\"max-height:400px;height: expression(this.height > 400 ? 400: true);\"
                src=\"{1}\"></a></div></td></tr>""").format(
                src_path, scr_path)

        if len(self._uadata) > 0:
            divid = strip_nonalphanum(self.remote_system)
            html += ("""<tr><td id={0} class="uabold" align="center" \
                colspan="2" onclick="toggleUA('{0}', '{1}');">
                Click to expand User Agents for {1}</td></tr>""").format(
                divid, self.remote_system)
            for ua_obj in sorted(self._uadata, key=lambda x: x.difference):
                html += ua_obj.create_table_html(divid)
            html += ("""<tr class="hide {0}"><td class="uared" align="center"\
             colspan="2" onclick="toggleUA('{0}', '{1}');">
            Click to collapse User Agents for {1}</td></tr>""").format(
                divid, self.remote_system)

        html += ("""</div>
        </div>""")
        return html

    def create_card_html(self):
        """Create a modern card-style HTML representation
        
        Returns:
            str: HTML card
        """
        scr_path = os.path.relpath(self.screenshot_path, self.root_path)
        src_path = os.path.relpath(self.source_path, self.root_path)
        
        # Determine card classes
        card_classes = ['url-card']
        has_creds = bool(self.default_creds)
        is_pwned = False
        
        # Check if pwned
        if self.credential_test_result and isinstance(self.credential_test_result, dict):
            successful = self.credential_test_result.get('successful_credentials', [])
            if successful:
                is_pwned = True
                card_classes.append('pwned')
        elif has_creds:
            card_classes.append('has-creds')
        
        # Get application name
        app_name = None
        if self.ai_application_info and isinstance(self.ai_application_info, dict):
            app_name = self.ai_application_info.get('application_name')
        elif self.default_creds and ' / ' in str(self.default_creds):
            app_name = str(self.default_creds).split(' / ')[0].strip()
        elif self.page_title and str(self.page_title) != 'Unknown':
            app_name = str(self.page_title)[:50]
        
        # Get category
        category = self.category or 'Uncategorized'
        
        html = f'<div class="{" ".join(card_classes)}" data-category="{category}" data-has-creds="{"true" if has_creds else "false"}">'
        
        # Header with URL and badges
        html += '<div class="url-header">'
        html += f'<div class="url-title"><a href="{self.remote_system}" target="_blank">{self.sanitize(self.remote_system)}</a></div>'
        html += '<div class="url-badges">'
        
        if is_pwned:
            html += '<span class="pwned-badge">🔓 PWNED!</span>'
        if has_creds:
            html += '<span class="cred-badge">🔑 Has Creds</span>'
        if self.credential_test_result and isinstance(self.credential_test_result, dict):
            if self.credential_test_result.get('tested', False):
                html += '<span class="cred-badge" style="background: #95a5a6;">✅ Tested</span>'
        
        html += f'<span class="category-tag">{category}</span>'
        html += '</div></div>'
        
        # Info grid
        html += '<div class="url-info">'
        
        # Application
        if app_name:
            html += f'<div class="info-item"><div class="info-label">Application</div><div class="info-value">{self.sanitize(app_name)}</div></div>'
        
        # Page Title
        if self.page_title and str(self.page_title) != 'Unknown':
            html += f'<div class="info-item"><div class="info-label">Page Title</div><div class="info-value">{self.sanitize(str(self.page_title))}</div></div>'
        
        # Default Credentials
        if self.default_creds:
            creds_display = str(self.default_creds)
            if ' / ' in creds_display:
                creds_display = creds_display.split(' / ')[-1]
            html += f'<div class="info-item"><div class="info-label">Default Credentials</div><div class="info-value" style="font-family: monospace; color: #e74c3c;">{self.sanitize(creds_display)}</div></div>'
        
        # Credential Test Results
        if self.credential_test_result and isinstance(self.credential_test_result, dict):
            result = self.credential_test_result
            if result.get('tested', False):
                successful = result.get('successful_credentials', [])
                if successful:
                    html += '<div class="info-item"><div class="info-label">Working Credentials</div><div class="info-value">'
                    for cred in successful:
                        username = cred.get('username', '')
                        password = cred.get('password', '')
                        html += f'<span style="font-family: monospace; color: #27ae60; font-weight: bold;">{self.sanitize(str(username))}:{self.sanitize(str(password))}</span><br>'
                    html += '</div></div>'
                else:
                    html += '<div class="info-item"><div class="info-label">Test Result</div><div class="info-value" style="color: #e74c3c;">❌ Failed</div></div>'
        
        # Resolved IP
        if self.resolved and self.resolved != 'Unknown':
            html += f'<div class="info-item"><div class="info-label">Resolved IP</div><div class="info-value">{self.sanitize(self.resolved)}</div></div>'
        
        html += '</div>'
        
        # Screenshot thumbnail with lightbox
        if os.path.isfile(self.screenshot_path) and not self.blank and not self.error_state:
            html += f'<div class="screenshot-container">'
            html += f'<img src="{scr_path}" alt="Screenshot" class="screenshot-thumbnail" '
            html += f'onclick="openLightbox(\'{scr_path}\')" '
            html += f'title="Click to view full size">'
            html += f'<div style="margin-top: 5px; font-size: 0.85em; color: #666;">Click thumbnail to enlarge</div>'
            html += '</div>'
        elif self.error_state:
            html += f'<div class="screenshot-container" style="color: #e74c3c; padding: 20px;">'
            html += f'❌ Error: {self.sanitize(str(self.error_state))}'
            html += '</div>'
        
        # Source code link
        if os.path.isfile(self.source_path):
            html += f'<div style="margin-top: 10px; text-align: center;">'
            html += f'<a href="{src_path}" target="_blank" style="color: #667eea;">View Source Code</a>'
            html += '</div>'
        
        html += '</div>'
        return html

    def sanitize(self, incoming_html):
        if type(incoming_html) == bytes:
            pass
        else:
            incoming_html = incoming_html.encode()
        return html.escape(incoming_html.decode(), quote=True)

    def add_ua_data(self, uaobject):
        difference = abs(len(self.source_code) - len(uaobject.source_code))
        if difference > self.max_difference:
            uaobject.difference = difference
            self._uadata.append(uaobject)

    @property
    def uadata(self):
        return self._uadata

    @uadata.setter
    def uadata(self, uadata):
        self._uadata = uadata


class UAObject(HTTPTableObject):

    """docstring for UAObject"""

    def __init__(self, browser, ua):
        super(UAObject, self).__init__()
        self._browser = browser
        self._ua = ua
        self._difference = None
        self._id = None
        self._parent = None

    @property
    def browser(self):
        return self._browser

    @browser.setter
    def browser(self, browser):
        self._browser = browser

    @property
    def difference(self):
        return self._difference

    @difference.setter
    def difference(self, difference):
        self._difference = difference

    @property
    def ua(self):
        return self._ua

    @ua.setter
    def ua(self, ua):
        self._ua = ua

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, id):
        self._id = id

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent):
        self._parent = parent

    def copy_data(self, http_object):
        self.remote_system = http_object.remote_system
        self.root_path = http_object.root_path
        self.parent = http_object.id
        super(UAObject, self).set_paths(self.root_path, self.browser)

    def create_table_html(self, divid):
        scr_path = os.path.relpath(self.screenshot_path, self.root_path)
        src_path = os.path.relpath(self.source_path, self.root_path)
        html = u""
        html += ("""<tr class="hide {0}">
        <td><div style=\"display: inline-block; width: 300px; word-wrap: break-word\">
        <a href=\"{1}\" target=\"_blank\">{1}</a><br>
        """).format(divid, self.remote_system)

        html += ("""
        <br>This request was different from the baseline.<br>
        The browser type is: <b>{0}</b><br><br>
        The user agent is: <b>{1}</b><br><br>
        Difference in length of the two webpage sources is\
        : <b>{2}</b><br>
        """).format(self.browser, self.ua, self.difference)

        if self.ssl_error:
            html += "<br><b>SSL Certificate error present on\
                     <a href=\"{0}\" target=\"_blank\">{0}</a></b><br>".format(
                self.remote_system)

        if self.default_creds is not None:
            try:
                html += "<br><b>Default credentials:</b> {0}<br>".format(
                    self.sanitize(self.default_creds))
            except UnicodeEncodeError:
                html += u"<br><b>Default credentials:</b> {0}<br>".format(
                    self.sanitize(self.default_creds))
                
        try:
            html += "\n<br><b> Page Title: </b>{0}\n".format(
                self.sanitize(self.page_title))
        except AttributeError:
            html += "\n<br><b> Page Title:</b>{0}\n".format(
                'Unable to Display')
        except UnicodeDecodeError:
            html += "\n<br><b> Page Title:</b>{0}\n".format(
                'Unable to Display')
        except UnicodeEncodeError:
                html += u'<br><b> Page Title: </b>{0}\n'.format(
                    self.sanitize(self.page_title))

        for key, value in self.headers.items():
            try:
                # Regular header display
                html += '<br><b> {0}:</b> {1}\n'.format(
                    self.sanitize(key), self.sanitize(value))
            except UnicodeEncodeError:
                html += u'<br><b> {0}:</b> {1}\n'.format(
                    self.sanitize(key), self.sanitize(value))

        if self.blank:
            html += ("""<br></td>
            <td><div style=\"display: inline-block; width: 850px;\">Page Blank,\
            Connection error, or SSL Issues</div></td>
            </tr>
            """)
        else:
            html += ("""<br><br><a href=\"{0}\"
                target=\"_blank\">Source Code</a></div></td>
                <td><div id=\"screenshot\"><a href=\"{1}\"
                target=\"_blank\"><img style=\"max-height:400px;height: expression(this.height > 400 ? 400: true);\"
                src=\"{1}\"></a></div></td></tr>""").format(
                src_path, scr_path)
        return html

