import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/api_client.dart';
import 'auth_model.dart';
import 'token_storage.dart';

abstract class AuthService {
  Future<TokenPair> login({
    required String email,
    required String password,
  });

  Future<AuthUser> currentUser();

  Future<void> logout({required String refreshToken});
}

class TokenPair {
  final String accessToken;
  final String refreshToken;

  const TokenPair({
    required this.accessToken,
    required this.refreshToken,
  });

  factory TokenPair.fromJson(Map<String, dynamic> json) {
    return TokenPair(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
    );
  }
}

class DioAuthService implements AuthService {
  final ApiClient _client;

  const DioAuthService(this._client);

  @override
  Future<TokenPair> login({
    required String email,
    required String password,
  }) async {
    final response = await _client.authDio.post(
      '/auth/login',
      data: {'email': email, 'password': password},
      options: Options(extra: {'skipAuth': true}),
    );
    return TokenPair.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  @override
  Future<AuthUser> currentUser() async {
    final response = await _client.authDio.get('/auth/me');
    return AuthUser.fromJson(Map<String, dynamic>.from(response.data as Map));
  }

  @override
  Future<void> logout({required String refreshToken}) async {
    await _client.authDio.post(
      '/auth/logout',
      data: {'refresh_token': refreshToken},
    );
  }
}

final authServiceProvider = Provider<AuthService>((ref) {
  return DioAuthService(ref.watch(apiClientProvider));
});

class AuthController extends StateNotifier<AuthState> {
  final TokenStorage _tokenStorage;
  final AuthService _authService;

  AuthController({
    required TokenStorage tokenStorage,
    required AuthService authService,
    ApiClient? apiClient,
  })  : _tokenStorage = tokenStorage,
        _authService = authService,
        super(const AuthState.loading()) {
    apiClient?.onSessionExpired = markSessionExpired;
  }

  Future<void> initialize() async {
    state = const AuthState.loading();
    if (!await _tokenStorage.hasCompleteSession()) {
      state = const AuthState.unauthenticated();
      return;
    }

    try {
      state = AuthState.authenticated(await _authService.currentUser());
    } catch (_) {
      await _tokenStorage.clear();
      state = const AuthState.unauthenticated();
    }
  }

  Future<bool> login({
    required String email,
    required String password,
  }) async {
    state = const AuthState.loading();
    try {
      final tokens = await _authService.login(email: email, password: password);
      await _tokenStorage.writeTokens(
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
      );
      state = AuthState.authenticated(await _authService.currentUser());
      return true;
    } on DioException catch (error) {
      await _tokenStorage.clear();
      state = AuthState.unauthenticated(errorMessage: _safeError(error));
      return false;
    } catch (_) {
      await _tokenStorage.clear();
      state = const AuthState.unauthenticated(
        errorMessage: 'Unable to sign in. Please try again.',
      );
      return false;
    }
  }

  Future<void> logout() async {
    final refreshToken = await _tokenStorage.readRefreshToken();
    try {
      if (refreshToken != null && refreshToken.isNotEmpty) {
        await _authService.logout(refreshToken: refreshToken);
      }
    } catch (_) {
      // Local credentials must still be removed when the server is unavailable.
    } finally {
      await _tokenStorage.clear();
      state = const AuthState.unauthenticated();
    }
  }

  Future<void> markSessionExpired() async {
    await _tokenStorage.clear();
    state = const AuthState.unauthenticated(
      errorMessage: 'Your session has expired. Please sign in again.',
    );
  }

  String _safeError(DioException error) {
    if (error.response?.statusCode == 401) {
      return 'Invalid email or password.';
    }
    return 'Unable to sign in. Please try again.';
  }
}

final authControllerProvider =
    StateNotifierProvider<AuthController, AuthState>((ref) {
  final client = ref.watch(apiClientProvider);
  return AuthController(
    tokenStorage: ref.watch(tokenStorageProvider),
    authService: ref.watch(authServiceProvider),
    apiClient: client,
  );
});
