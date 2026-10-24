import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../auth/auth_controller.dart';
import '../auth/login_screen.dart';
import '../auth/change_password_screen.dart';
import '../admin/admin_users_screen.dart';
import '../auth/auth_model.dart';
import '../settings/settings_screen.dart';
import '../documents/documents_screen.dart';
import '../documents/document_view_screen.dart';
import '../review/review_screen.dart';
import '../labs/labs_screen.dart';
import '../labs/lab_detail_screen.dart';
import '../ask/ask_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';




final _rootNavigatorKey = GlobalKey<NavigatorState>();

final _shellNavigatorKey = GlobalKey<NavigatorState>();

class ScaffoldWithResponsiveNav extends StatelessWidget {
  final Widget child;

  const ScaffoldWithResponsiveNav({super.key, required this.child});

  int _calculateSelectedIndex(BuildContext context) {
    try {
      final location = GoRouterState.of(context).uri.toString();
      if (location.startsWith('/labs')) return 1;
      if (location.startsWith('/ask')) return 2;
      if (location.startsWith('/settings')) return 3;
    } catch (_) {}
    return 0; // /documents default
  }


  void _onItemTapped(int index, BuildContext context) {
    switch (index) {
      case 0:
        context.go('/documents');
        break;
      case 1:
        context.go('/labs');
        break;
      case 2:
        context.go('/ask');
        break;
      case 3:
        context.go('/settings');
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    final selectedIndex = _calculateSelectedIndex(context);

    // Responsive layouts:
    // < 600 px (mobile): BottomNavigationBar
    // 600 - 1024 px (tablet): NavigationRail
    // > 1024 px (desktop): Side NavigationDrawer / Rail expanded
    if (width < 600) {
      return Scaffold(
        body: _InstallBannerWrapper(child: child),
        bottomNavigationBar: NavigationBar(
          selectedIndex: selectedIndex,
          onDestinationSelected: (idx) => _onItemTapped(idx, context),
          destinations: const [
            NavigationDestination(icon: Icon(Icons.description_outlined), selectedIcon: Icon(Icons.description), label: 'Documents'),
            NavigationDestination(icon: Icon(Icons.show_chart_outlined), selectedIcon: Icon(Icons.show_chart), label: 'Labs'),
            NavigationDestination(icon: Icon(Icons.chat_bubble_outline), selectedIcon: Icon(Icons.chat_bubble), label: 'Ask'),
            NavigationDestination(icon: Icon(Icons.settings_outlined), selectedIcon: Icon(Icons.settings), label: 'Settings'),
          ],
        ),
        floatingActionButton: _logoutButton(context),
      );
    } else {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              extended: width > 1024,
              selectedIndex: selectedIndex,
              onDestinationSelected: (idx) => _onItemTapped(idx, context),
              leading: Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Row(
                  children: [
                    const Icon(Icons.health_and_safety, color: Color(0xFF0D9488), size: 32),
                    if (width > 1024) ...[
                      const SizedBox(width: 8),
                      const Text('SwasthyaStats', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Color(0xFF0D9488))),
                    ],
                  ],
                ),
              ),
              destinations: const [
                NavigationRailDestination(icon: Icon(Icons.description_outlined), selectedIcon: Icon(Icons.description), label: Text('Documents')),
                NavigationRailDestination(icon: Icon(Icons.show_chart_outlined), selectedIcon: Icon(Icons.show_chart), label: Text('Labs')),
                NavigationRailDestination(icon: Icon(Icons.chat_bubble_outline), selectedIcon: Icon(Icons.chat_bubble), label: Text('Ask (RAG)')),
                NavigationRailDestination(icon: Icon(Icons.settings_outlined), selectedIcon: Icon(Icons.settings), label: Text('Settings')),
              ],
            ),
            const VerticalDivider(thickness: 1, width: 1),
            Expanded(child: _InstallBannerWrapper(child: child)),
          ],
        ),
        floatingActionButton: _logoutButton(context),
      );

    }

  }

  Widget _logoutButton(BuildContext context) {
    return Consumer(
      builder: (context, ref, child) => FloatingActionButton.small(
        heroTag: 'logout',
        tooltip: 'Log out',
        onPressed: () => ref.read(authControllerProvider.notifier).logout(),
        child: const Icon(Icons.logout),
      ),
    );
  }
}

class _InstallBannerWrapper extends StatefulWidget {

  final Widget child;
  const _InstallBannerWrapper({required this.child});

  @override
  State<_InstallBannerWrapper> createState() => _InstallBannerWrapperState();
}

class _InstallBannerWrapperState extends State<_InstallBannerWrapper> {
  bool _dismissed = false;

  @override

  void initState() {
    super.initState();
    _checkDismissed();
  }

  Future<void> _checkDismissed() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final dismissed = prefs.getBool('install_hint_dismissed') ?? false;
      if (mounted) setState(() => _dismissed = dismissed);
    } catch (_) {}
  }

  Future<void> _dismiss() async {
    setState(() => _dismissed = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool('install_hint_dismissed', true);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_dismissed) return widget.child;

    return Column(
      children: [
        MaterialBanner(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          leading: const Icon(Icons.install_mobile, color: Color(0xFF0D9488)),
          content: const Text('Install SwasthyaStats: tap browser menu (⋮) → Add to Home Screen'),
          actions: [
            TextButton(
              onPressed: _dismiss,
              child: const Text('Dismiss', style: TextStyle(color: Color(0xFF0D9488))),
            ),
          ],
        ),
        Expanded(child: widget.child),
      ],
    );
  }
}


// Placeholder screens for features built in Week 5

class LabsPlaceholderScreen extends StatelessWidget {
  const LabsPlaceholderScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Lab Trend Charts')),
      body: const Center(
        child: Text('Lab Trend Charts with Reference Bands (Week 4 target)', textAlign: TextAlign.center),
      ),
    );
  }
}

class AskPlaceholderScreen extends StatelessWidget {
  const AskPlaceholderScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Ask (RAG)')),
      body: const Center(
        child: Text('Ask questions with citation chips (Week 5 target)', textAlign: TextAlign.center),
      ),
    );
  }
}

GoRouter createAppRouter(WidgetRef ref) {
  final refresh = _AuthRouterRefresh(ref);
  return GoRouter(
    navigatorKey: _rootNavigatorKey,
    initialLocation: '/documents',
    refreshListenable: refresh,
    redirect: (context, state) {
      final authState = ref.read(authControllerProvider);
      return authRedirect(
        authState: authState,
        location: state.matchedLocation,
        requestedLocation: state.uri.toString(),
        redirectTarget: state.uri.queryParameters['redirect'],
      );
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/change-password',
        builder: (context, state) => const ChangePasswordScreen(),
      ),
      GoRoute(
        path: '/admin/users',
        builder: (context, state) => const AdminUsersScreen(),
      ),
    ShellRoute(
      navigatorKey: _shellNavigatorKey,
      builder: (context, state, child) => ScaffoldWithResponsiveNav(child: child),
      routes: [
        GoRoute(
          path: '/documents',
          builder: (context, state) => const DocumentsScreen(),
          routes: [
            GoRoute(
              path: ':id',
              builder: (context, state) {
                final id = int.tryParse(state.pathParameters['id'] ?? '1') ?? 1;
                return DocumentViewScreen(documentId: id);
              },
              routes: [
                GoRoute(
                  path: 'review',
                  builder: (context, state) {
                    final id = int.tryParse(state.pathParameters['id'] ?? '1') ?? 1;
                    return ReviewScreen(documentId: id);
                  },
                ),
              ],
            ),
          ],
        ),
        GoRoute(
          path: '/labs',
          builder: (context, state) => const LabsScreen(),
          routes: [
            GoRoute(
              path: ':test',
              builder: (context, state) {
                final test = Uri.decodeComponent(state.pathParameters['test'] ?? '');
                return LabDetailScreen(testName: test);
              },
            ),
          ],
        ),
        GoRoute(path: '/ask', builder: (context, state) => const AskScreen()),
        GoRoute(path: '/settings', builder: (context, state) => const SettingsScreen()),

      ],
    ),
    ],
  );
}

String? authRedirect({
  required AuthState authState,
  required String location,
  required String requestedLocation,
  String? redirectTarget,
}) {
  final isLogin = location == '/login';
  final isChangePassword = location == '/change-password';
  if (authState.status == AuthStatus.loading) {
    return isLogin ? null : '/login';
  }
  if (!authState.isAuthenticated && !isLogin) {
    return '/login?redirect=${Uri.encodeComponent(requestedLocation)}';
  }
  if (authState.isAuthenticated && authState.user!.mustChangePassword) {
    if (!isChangePassword) {
      return '/change-password?redirect=${Uri.encodeComponent(requestedLocation)}';
    }
    return null;
  }
  if (authState.isAuthenticated && isChangePassword) {
    return redirectTarget ?? '/documents';
  }
  if (location == '/admin/users' && !authState.user!.isAdmin) {
    return '/documents';
  }
  if (authState.isAuthenticated && isLogin) {
    return redirectTarget ?? '/documents';
  }
  return null;
}

class _AuthRouterRefresh extends ChangeNotifier {
  _AuthRouterRefresh(WidgetRef ref) {
    ref.listen<AuthState>(
      authControllerProvider,
      (previous, next) => notifyListeners(),
    );
  }
}
