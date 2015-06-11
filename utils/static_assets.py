

class StaticTemplates:

    def gen_redirect(self, redirect_to):
        """
        Redirect user to `redirect_to` location
        """
        html = '''
            <!DOCTYPE HTML>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="1; url=''' + redirect_to + '''">
            <script>
              window.location.href = "''' + redirect_to + '''"
            </script>
            <title>Page Redirection</title>
            If you are not redirected automatically, follow the <a href="''' + redirect_to + '''">'''+redirect_to+'''</a>
            '''
        return html

    def gen_frame(self, style):
        """
        Used as a template to include the needed file
        """
        html = '''
            <html>
              <head>
                <link rel="stylesheet" type="text/css" href="/assets/css/styles.css">
                <script src="/assets/js/jquery.js"></script>
                <script src="/assets/js/functions.js"></script>
                <script>
                $( document ).ready(function() {
                  $("#includedContent").load("/assets/templates/''' + style + '''.html");
                });
                </script>
              </head>
              <body>
                 <div id="includedContent"></div>
              </body>
            </html>
        '''
        return html
