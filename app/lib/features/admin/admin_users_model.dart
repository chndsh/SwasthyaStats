class AdminUser {
  final int id;
  final String email;
  final String? displayName;
  final bool isAdmin;
  final bool mustChangePassword;

  const AdminUser({
    required this.id,
    required this.email,
    required this.displayName,
    required this.isAdmin,
    required this.mustChangePassword,
  });

  factory AdminUser.fromJson(Map<String, dynamic> json) => AdminUser(
        id: json['id'] as int,
        email: json['email'] as String,
        displayName: json['display_name'] as String?,
        isAdmin: json['is_admin'] as bool? ?? false,
        mustChangePassword: json['must_change_password'] as bool? ?? false,
      );
}

class TemporaryPasswordResponse {
  final AdminUser user;
  final String temporaryPassword;

  const TemporaryPasswordResponse({
    required this.user,
    required this.temporaryPassword,
  });
}
