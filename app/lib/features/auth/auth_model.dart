class AuthUser {
  final int id;
  final String email;
  final String? displayName;
  final bool isAdmin;

  const AuthUser({
    required this.id,
    required this.email,
    this.displayName,
    required this.isAdmin,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) => AuthUser(
        id: json['id'] as int,
        email: json['email'] as String,
        displayName: json['display_name'] as String?,
        isAdmin: json['is_admin'] as bool? ?? false,
      );
}
