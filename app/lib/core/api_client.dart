import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:flutter/foundation.dart';

const String kDefaultApiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: kIsWeb ? '/api/v1' : 'http://localhost:8000/api/v1',
);

class ApiClient {
  late final Dio dio;
  String _apiKey = 'change-me';

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

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          options.headers['X-API-Key'] = _apiKey;
          return handler.next(options);
        },
      ),
    );
  }

  void setApiKey(String key) {
    _apiKey = key;
  }

  String get apiKey => _apiKey;

  void setBaseUrl(String url) {
    dio.options.baseUrl = url;
  }

  String get baseUrl => dio.options.baseUrl;
}

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient();
});
