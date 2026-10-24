import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import 'admin_users_model.dart';

class AdminUsersState {
  final AsyncValue<List<AdminUser>> users;
  final String? temporaryPassword;

  const AdminUsersState({required this.users, this.temporaryPassword});

  AdminUsersState copyWith({
    AsyncValue<List<AdminUser>>? users,
    String? temporaryPassword,
    bool clearTemporaryPassword = false,
  }) => AdminUsersState(
    users: users ?? this.users,
    temporaryPassword: clearTemporaryPassword
        ? null
        : temporaryPassword ?? this.temporaryPassword,
  );
}

class AdminUsersController extends StateNotifier<AdminUsersState> {
  final ApiClient _client;

  AdminUsersController(this._client)
    : super(const AdminUsersState(users: AsyncValue.loading())) {
    load();
  }

  Future<void> load() async {
    try {
      final response = await _client.dio.get('/auth/users');
      final users = (response.data as List)
          .map(
            (item) =>
                AdminUser.fromJson(Map<String, dynamic>.from(item as Map)),
          )
          .toList();
      state = state.copyWith(users: AsyncValue.data(users));
    } catch (error, stackTrace) {
      state = state.copyWith(users: AsyncValue.error(error, stackTrace));
    }
  }

  Future<bool> create({
    required String email,
    required String password,
    String? displayName,
  }) async {
    try {
      final response = await _client.dio.post(
        '/auth/users',
        data: {
          'email': email,
          'password': password,
          'display_name': displayName,
        },
      );
      final user = AdminUser.fromJson(
        Map<String, dynamic>.from(response.data as Map),
      );
      state = state.copyWith(
        users: AsyncValue.data([...state.users.value ?? [], user]),
        temporaryPassword: password,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> reset(int userId, String password) async {
    try {
      await _client.dio.put(
        '/auth/users/$userId/password',
        data: {'password': password},
      );
      state = state.copyWith(temporaryPassword: password);
      await load();
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<bool> delete(int userId) async {
    try {
      await _client.dio.delete('/auth/users/$userId');
      await load();
      return true;
    } on DioException {
      return false;
    }
  }

  void clearTemporaryPassword() {
    state = state.copyWith(clearTemporaryPassword: true);
  }
}

final adminUsersControllerProvider =
    StateNotifierProvider<AdminUsersController, AdminUsersState>(
      (ref) => AdminUsersController(ref.watch(apiClientProvider)),
    );
