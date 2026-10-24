import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';
import 'auth_model.dart';

final authControllerProvider =
    StateNotifierProvider<AuthController, AsyncValue<AuthUser?>>(
  (ref) => AuthController(ref.read(apiClientProvider), const FlutterSecureStorage()),
);

class AuthController extends StateNotifier<AsyncValue<AuthUser?>> {
  final ApiClient api;
  final FlutterSecureStorage storage;

  AuthController(this.api, this.storage) : super(const AsyncData(null));

  Future<void> login(String email, String password) async {
    state = const AsyncLoading();
    try {
      final response = await api.auth.post('/login', data: {
        'email': email,
        'password': password,
      });
      await storage.write(key: 'access_token', value: response.data['access_token']);
      await storage.write(key: 'refresh_token', value: response.data['refresh_token']);
      await loadFromStorage();
    } catch (error, stack) {
      state = AsyncError(error, stack);
      rethrow;
    }
  }

  Future<void> loadFromStorage() async {
    final token = await storage.read(key: 'access_token');
    if (token == null) {
      state = const AsyncData(null);
      return;
    }
    try {
      final response = await api.auth.get(
        '/me',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      state = AsyncData(AuthUser.fromJson(response.data));
    } catch (_) {
      await storage.deleteAll();
      state = const AsyncData(null);
    }
  }

  Future<void> logout() async {
    try {
      final refresh = await storage.read(key: 'refresh_token');
      if (refresh != null) {
        await api.auth.post('/logout', data: {'refresh_token': refresh});
      }
    } catch (_) {}
    await storage.deleteAll();
    state = const AsyncData(null);
  }
}
