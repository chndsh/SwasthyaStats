import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:app/features/labs/lab_detail_screen.dart';
import 'package:app/features/labs/lab_chart_controller.dart';
import 'package:app/features/labs/labs_controller.dart';

class FakeLabChartController extends LabChartController {
  final LabChartData _data;
  FakeLabChartController(this._data);

  @override
  Future<LabChartData> build(String testName) async {
    return _data;
  }
}

class FakeFavouritesNotifier extends LabFavouritesNotifier {
  FakeFavouritesNotifier(super.initial);

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
  testWidgets('LabDetailScreen renders chart and history table', (tester) async {
    final sampleData = LabChartData(
      testName: 'HbA1c',
      refLow: 4.0,
      refHigh: 5.6,
      unit: '%',
      points: [
        ChartPoint(
          date: DateTime(2026, 1, 15),
          value: 7.1,
          flag: 'high',
          documentId: 10,
          pageNo: 1,
        ),
        ChartPoint(
          date: DateTime(2026, 6, 15),
          value: 6.8,
          flag: 'high',
          documentId: 11,
          pageNo: 1,
        ),
      ],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          labChartProvider.overrideWith(() => FakeLabChartController(sampleData)),
          labFavouritesProvider.overrideWith((ref) => FakeFavouritesNotifier({'HbA1c'})),
        ],
        child: const MaterialApp(
          home: LabDetailScreen(testName: 'HbA1c'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('HbA1c'), findsOneWidget);
    expect(find.byType(LineChart), findsOneWidget);
    expect(find.text('RECORD HISTORY'), findsOneWidget);
    expect(find.text('7.1 %'), findsOneWidget);
    expect(find.text('6.8 %'), findsOneWidget);
    expect(find.byType(DataTable), findsOneWidget);
  });

  testWidgets('Empty points show no-data message', (tester) async {
    final emptyData = LabChartData(
      testName: 'Glucose',
      refLow: 70.0,
      refHigh: 99.0,
      unit: 'mg/dL',
      points: [],
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          labChartProvider.overrideWith(() => FakeLabChartController(emptyData)),
          labFavouritesProvider.overrideWith((ref) => FakeFavouritesNotifier({})),
        ],
        child: const MaterialApp(
          home: LabDetailScreen(testName: 'Glucose'),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No readings available for Glucose'), findsOneWidget);
  });
}
