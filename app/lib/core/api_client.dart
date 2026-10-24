import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/foundation.dart';
import '../features/auth/token_storage.dart';

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
  late final Dio authDio;
  final TokenStorage tokenStorage;
  Future<void> Function()? onSessionExpired;
  Future<void>? _refreshFuture;

  ApiClient({
    String baseUrl = kDefaultApiBase,
    TokenStorage? storage,
  }) : tokenStorage = storage ?? SecureTokenStorage() {
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
    authDio = Dio(
      BaseOptions(
        baseUrl: _authBaseUrl(baseUrl),
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );
    authDio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          if (options.extra['skipAuth'] != true) {
            final accessToken = await tokenStorage.readAccessToken();
            if (accessToken != null && accessToken.isNotEmpty) {
              options.headers['Authorization'] = 'Bearer $accessToken';
            }
          }
          return handler.next(options);
        },
      ),
    );

    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          if (options.extra['skipAuth'] == true) {
            return handler.next(options);
          }
          final accessToken = await tokenStorage.readAccessToken();
          if (accessToken != null && accessToken.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $accessToken';
          }
          return handler.next(options);
        },
        onError: (error, handler) async {
          final request = error.requestOptions;
          if (error.response?.statusCode != 401 ||
              request.extra['skipAuth'] == true ||
              request.extra['retriedAfterRefresh'] == true) {
            return handler.next(error);
          }

          try {
            await _refreshAccessToken();
            final accessToken = await tokenStorage.readAccessToken();
            if (accessToken == null || accessToken.isEmpty) {
              return handler.next(error);
            }
            request.extra['retriedAfterRefresh'] = true;
            request.headers['Authorization'] = 'Bearer $accessToken';
            final response = await dio.fetch(request);
            return handler.resolve(response);
          } catch (_) {
            await tokenStorage.clear();
            await onSessionExpired?.call();
            return handler.next(error);
          }
        },
      ),
    );
  }

  Future<void> _refreshAccessToken() {
    final pending = _refreshFuture;
    if (pending != null) return pending;

    final refresh = _performRefresh();
    _refreshFuture = refresh;
    refresh.then(
      (_) {
        if (identical(_refreshFuture, refresh)) _refreshFuture = null;
      },
      onError: (Object _, StackTrace _) {
        if (identical(_refreshFuture, refresh)) _refreshFuture = null;
      },
    );
    return refresh;
  }

  Future<void> _performRefresh() async {
    final refreshToken = await tokenStorage.readRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) {
      throw StateError('No refresh token available');
    }
    final response = await authDio.post(
      '/auth/refresh',
      data: {'refresh_token': refreshToken},
    );
    final data = Map<String, dynamic>.from(response.data as Map);
    await tokenStorage.writeTokens(
      accessToken: data['access_token'] as String,
      refreshToken: data['refresh_token'] as String,
    );
  }

  String _authBaseUrl(String apiBaseUrl) {
    final normalized = apiBaseUrl.replaceFirst(RegExp(r'/+$'), '');
    if (normalized.endsWith('/api/v1')) {
      final root = normalized.substring(0, normalized.length - '/api/v1'.length);
      return root.isEmpty ? '/' : root;
    }
    return normalized;
  }

  void setBaseUrl(String url) {
    dio.options.baseUrl = url;
  }

  String get baseUrl => dio.options.baseUrl;
}

final apiClientProvider = Provider<ApiClient>((ref) {
  return ApiClient(storage: ref.watch(tokenStorageProvider));
});
