import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/features/labs/labs_screen.dart';
import 'package:app/features/labs/labs_controller.dart';
import 'package:app/features/labs/lab_model.dart';

class FakeLabsController extends LabsController {
  final List<LabTestSummary> _items;
  FakeLabsController(this._items);

  @override
  Future<List<LabTestSummary>> build() async {
    return _items;
  }
}

class FakeFavouritesNotifier extends LabFavouritesNotifier {
  FakeFavouritesNotifier(Set<String> initial) : super(initial);

  @override
  Future<void> toggle(String testName) async {
    if (state.contains(testName)) {
      state = {...state}..remove(testName);
    } else {
      state = {...state, testName};
    }
  }
}

void main() {
  testWidgets('LabsScreen shows test list and favourite section', (tester) async {
    final sampleTests = [
      LabTestSummary(
        testName: 'HbA1c',
        canonicalTestId: 'hba1c',
        count: 2,
        latestValue: 6.8,
        latestUnit: '%',
        latestFlag: 'high',
        latestDate: '2026-06-15',
        refLow: 4.0,
        refHigh: 5.6,
      ),
      LabTestSummary(
        testName: 'Fasting Glucose',
        canonicalTestId: 'glucose_fasting',
        count: 1,
        latestValue: 95.0,
        latestUnit: 'mg/dL',
        latestFlag: 'normal',
        latestDate: '2026-06-15',
        refLow: 70.0,
        refHigh: 99.0,
      ),
    ];

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          labsControllerProvider.overrideWith(() => FakeLabsController(sampleTests)),
          labFavouritesProvider.overrideWith((ref) => FakeFavouritesNotifier({'HbA1c'})),
        ],
        child: const MaterialApp(home: LabsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('HbA1c'), findsAtLeastNWidgets(1));
    expect(find.text('Fasting Glucose'), findsOneWidget);
    expect(find.text('FAVORITE TRENDS'), findsOneWidget);
    expect(find.text('ALL RECORDED TESTS'), findsOneWidget);
  });

  testWidgets('LabsScreen shows empty state placeholder when list is empty', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          labsControllerProvider.overrideWith(() => FakeLabsController([])),
          labFavouritesProvider.overrideWith((ref) => FakeFavouritesNotifier({})),
        ],
        child: const MaterialApp(home: LabsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No confirmed lab tests yet'), findsOneWidget);
  });
}
