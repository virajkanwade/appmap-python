import json

# from werkzeug.wrappers import Request

from appmap._implementation import env
from appmap._implementation import generation
from appmap._implementation.recording import Recording


class AppmapFlask:
    def __init__(self, app):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        if not env.enabled():
            return

        self.recording = Recording()

        self.record_url = '/_appmap/record'

        print('in init_app')
        app.add_url_rule(self.record_url, 'appmap_record_get', view_func=self.record_get, methods=['GET'])
        app.add_url_rule(self.record_url, 'appmap_record_post', view_func=self.record_post, methods=['POST'])
        app.add_url_rule(self.record_url, 'appmap_record_delete', view_func=self.record_delete, methods=['DELETE'])

        # app.wsgi_app = AppmapFlaskMiddleware(app.wsgi_app)
        # app.teardown_appcontext(self.teardown)

    # def teardown(self, exception):
    #     print('in teardown', exception)
    #     # ctx = _app_ctx_stack.top
    #     # if hasattr(ctx, 'appmap_recording_enabled'):
    #     #     ctx.appmap_recording_enabled = False

    def record_get(self):
        return {'enabled': self.recording.is_running()}

    def record_post(self):
        if self.recording.is_running():
            return 'Recording is already in progress', 409

        self.recording.start()
        return '', 200

    def record_delete(self):
        if not self.recording.is_running():
            return 'No recording is in progress', 404

        self.recording.stop()

        return json.loads(generation.dump(self.recording))


# class AppmapFlaskMiddleware:
#     def __init__(self, app):
#         self.app = app
#
#     def __call__(self, environ, start_response):
#         # werkzeug Request not flask
#         request = Request(environ)
#
#         print(request.url)
#
#         return self.app(environ, start_response)
