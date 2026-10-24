import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

// In production web builds Flutter is served from the same origin as the API,
// so a relative path works. In development the Flutter dev server runs on a
// different port (:3000) than the API (:8000), so we need the absolute URL.
const String kDefaultApiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: kReleaseMode
      ? '/api/v1'
      : 'http://localhost:8000/api/v1',
);

class ApiClient {
  late final Dio dio;
  late final Dio auth;
  ApiClient({String baseUrl = kDefaultApiBase}) {
    dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );
    auth = Dio(
      BaseOptions(
        baseUrl: baseUrl.replaceFirst(RegExp(r'/api/v1/?$'), ''),
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );
    final storage = const FlutterSecureStorage();
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await storage.read(key: 'access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          handler.next(options);
        },
        onError: (error, handler) async {
          if (error.response?.statusCode != 401 ||
              error.requestOptions.extra['authRetry'] == true) {
            handler.next(error);
            return;
          }
          final refresh = await storage.read(key: 'refresh_token');
          if (refresh == null) {
            handler.next(error);
            return;
          }
          try {
            final response = await auth.post('/refresh', data: {'refresh_token': refresh});
            await storage.write(key: 'access_token', value: response.data['access_token']);
            await storage.write(key: 'refresh_token', value: response.data['refresh_token']);
            final request = error.requestOptions;
            request.extra['authRetry'] = true;
            request.headers['Authorization'] = 'Bearer ${response.data['access_token']}';
            handler.resolve(await dio.fetch(request));
          } catch (_) {
            await storage.deleteAll();
            handler.next(error);
          }
        },
      ),
    );
  }

  @Deprecated('JWT authentication is managed by AuthController')
  void setApiKey(String key) {}

  @Deprecated('JWT authentication replaced API keys')
  String get apiKey => '';

  void setBaseUrl(String url) {
    dio.options.baseUrl = url;
  }

  String get baseUrl => dio.options.baseUrl;
}

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient();
});
