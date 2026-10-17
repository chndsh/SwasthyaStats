import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../settings/settings_screen.dart';
import '../documents/documents_screen.dart';
import '../documents/document_view_screen.dart';
import '../review/review_screen.dart';
import '../labs/labs_screen.dart';
import '../labs/lab_detail_screen.dart';

final _rootNavigatorKey = GlobalKey<NavigatorState>();

final _shellNavigatorKey = GlobalKey<NavigatorState>();

class ScaffoldWithResponsiveNav extends StatelessWidget {
  final Widget child;

  const ScaffoldWithResponsiveNav({super.key, required this.child});

  int _calculateSelectedIndex(BuildContext context) {
    final location = GoRouterState.of(context).uri.toString();
    if (location.startsWith('/labs')) return 1;
    if (location.startsWith('/ask')) return 2;
    if (location.startsWith('/settings')) return 3;
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
        body: child,
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
            Expanded(child: child),
          ],
        ),
      );
    }
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

final appRouter = GoRouter(
  navigatorKey: _rootNavigatorKey,
  initialLocation: '/settings',
  routes: [
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
        GoRoute(path: '/ask', builder: (context, state) => const AskPlaceholderScreen()),
        GoRoute(path: '/settings', builder: (context, state) => const SettingsScreen()),
      ],
    ),
  ],
);

