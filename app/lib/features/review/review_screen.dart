import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/api_client.dart';
import 'observation_model.dart';
import 'review_controller.dart';

class ReviewScreen extends ConsumerStatefulWidget {
  final int documentId;

  const ReviewScreen({super.key, required this.documentId});

  @override
  ConsumerState<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends ConsumerState<ReviewScreen> {
  Uint8List? _imageBytes;
  bool _isLoadingImage = false;
  int _loadedPageNo = -1;

  Future<void> _loadPageImage(int pageNo) async {
    if (_loadedPageNo == pageNo && _imageBytes != null) return;
    setState(() => _isLoadingImage = true);

    try {
      final client = ref.read(apiClientProvider);
      final resp = await client.dio.get<List<int>>(
        '/documents/${widget.documentId}/pages/$pageNo.png',
        options: Options(responseType: ResponseType.bytes),
      );
      if (mounted) {
        setState(() {
          _imageBytes = Uint8List.fromList(resp.data!);
          _loadedPageNo = pageNo;
          _isLoadingImage = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _imageBytes = null;
          _isLoadingImage = false;
        });
      }
    }
  }

  Color _getConfidenceColor(double? conf) {
    if (conf == null) return Colors.grey;
    if (conf >= 0.8) return Colors.green;
    if (conf >= 0.6) return Colors.amber.shade700;
    return Colors.red;
  }

  void _showEditDialog(BuildContext context, ObservationModel obs) {
    final nameCtrl = TextEditingController(text: obs.testName);
    final valCtrl = TextEditingController(
      text: obs.valueNum != null ? obs.valueNum.toString() : (obs.valueText ?? ''),
    );
    final unitCtrl = TextEditingController(text: obs.unit ?? '');
    final lowCtrl = TextEditingController(text: obs.refLow?.toString() ?? '');
    final highCtrl = TextEditingController(text: obs.refHigh?.toString() ?? '');
    String? selectedFlag = obs.flag;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Text('Edit ${obs.testName}'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  decoration: const InputDecoration(labelText: 'Test Name'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: valCtrl,
                  decoration: const InputDecoration(labelText: 'Value (numeric or text)'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: unitCtrl,
                  decoration: const InputDecoration(labelText: 'Unit'),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: lowCtrl,
                        decoration: const InputDecoration(labelText: 'Ref Low'),
                        keyboardType: TextInputType.number,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: highCtrl,
                        decoration: const InputDecoration(labelText: 'Ref High'),
                        keyboardType: TextInputType.number,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  value: selectedFlag,
                  decoration: const InputDecoration(labelText: 'Flag'),
                  items: const [
                    DropdownMenuItem(value: null, child: Text('None / Normal')),
                    DropdownMenuItem(value: 'low', child: Text('Low')),
                    DropdownMenuItem(value: 'high', child: Text('High')),
                    DropdownMenuItem(value: 'critical', child: Text('Critical')),
                  ],
                  onChanged: (val) => setDialogState(() => selectedFlag = val),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () async {
                final double? numVal = double.tryParse(valCtrl.text.trim());
                final patch = <String, dynamic>{
                  'test_name': nameCtrl.text.trim(),
                  'value_num': numVal,
                  'value_text': numVal == null ? valCtrl.text.trim() : null,
                  'unit': unitCtrl.text.trim().isEmpty ? null : unitCtrl.text.trim(),
                  'ref_low': double.tryParse(lowCtrl.text.trim()),
                  'ref_high': double.tryParse(highCtrl.text.trim()),
                  'flag': selectedFlag,
                };
                Navigator.pop(ctx);
                await ref
                    .read(reviewControllerProvider(widget.documentId).notifier)
                    .updateObservation(obs.id, patch);
              },
              child: const Text('Save'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImagePane(ReviewState state) {
    if (_loadedPageNo != state.selectedPageNo && !_isLoadingImage) {
      _loadedPageNo = state.selectedPageNo;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _loadPageImage(state.selectedPageNo);
      });
    }

    return Container(
      color: Colors.black12,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (_imageBytes != null)
            InteractiveViewer(
              minScale: 0.8,
              maxScale: 4.0,
              child: Center(
                child: Image.memory(
                  _imageBytes!,
                  fit: BoxFit.contain,
                ),
              ),
            )
          else if (!_isLoadingImage)
            const Center(
              child: Text('Page image unavailable'),
            ),
          if (_isLoadingImage)
            const Center(child: CircularProgressIndicator()),
          Positioned(
            top: 8,
            right: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                'Page ${state.selectedPageNo}',
                style: const TextStyle(color: Colors.white, fontSize: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildObservationsList(ReviewState state) {
    final isConfirmed = state.status == 'confirmed';

    return ListView.builder(
      padding: const EdgeInsets.all(8),
      itemCount: state.observations.length,
      itemBuilder: (ctx, i) {
        final obs = state.observations[i];
        final isSelected = obs.id == state.selectedObservationId;
        final confColor = _getConfidenceColor(obs.confidence);

        return Card(
          elevation: isSelected ? 3 : 1,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: isSelected
                ? BorderSide(color: Theme.of(context).primaryColor, width: 2)
                : BorderSide.none,
          ),
          margin: const EdgeInsets.symmetric(vertical: 4),
          child: ListTile(
            leading: CircleAvatar(
              radius: 6,
              backgroundColor: confColor,
            ),
            title: Text(
              obs.testName,
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 2),
                Text(
                  'Value: ${obs.valueNum != null ? obs.valueNum.toString() : (obs.valueText ?? "-")} ${obs.unit ?? ""}',
                  style: const TextStyle(fontSize: 13),
                ),
                if (obs.refLow != null || obs.refHigh != null)
                  Text(
                    'Ref: ${obs.refLow ?? "-"} - ${obs.refHigh ?? "-"}',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
              ],
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (obs.flag != null && obs.flag != 'normal')
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    margin: const EdgeInsets.only(right: 8),
                    decoration: BoxDecoration(
                      color: obs.flag == 'critical'
                          ? Colors.red.shade100
                          : Colors.amber.shade100,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      obs.flag!.toUpperCase(),
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: obs.flag == 'critical'
                            ? Colors.red.shade800
                            : Colors.amber.shade900,
                      ),
                    ),
                  ),
                if (!isConfirmed)
                  IconButton(
                    icon: const Icon(Icons.edit_outlined, size: 20),
                    onPressed: () => _showEditDialog(context, obs),
                  ),
              ],
            ),
            onTap: () {
              ref
                  .read(reviewControllerProvider(widget.documentId).notifier)
                  .selectObservation(obs);
              _loadPageImage(obs.pageNo);
            },
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final reviewAsync = ref.watch(reviewControllerProvider(widget.documentId));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Review Observations'),
        actions: [
          reviewAsync.when(
            data: (state) => Container(
              margin: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: state.status == 'confirmed'
                    ? Colors.green.shade100
                    : Colors.amber.shade100,
                borderRadius: BorderRadius.circular(6),
              ),
              child: Text(
                state.status.toUpperCase(),
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: state.status == 'confirmed'
                      ? Colors.green.shade800
                      : Colors.amber.shade900,
                ),
              ),
            ),
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
          ),
        ],
      ),
      body: reviewAsync.when(
        data: (state) {
          if (state.observations.isEmpty) {
            return const Center(child: Text('No extracted observations found'));
          }

          return LayoutBuilder(
            builder: (ctx, constraints) {
              final isWide = constraints.maxWidth >= 700;

              return Column(
                children: [
                  Expanded(
                    child: isWide
                        ? Row(
                            children: [
                              Expanded(
                                flex: 5,
                                child: _buildImagePane(state),
                              ),
                              const VerticalDivider(width: 1),
                              Expanded(
                                flex: 5,
                                child: _buildObservationsList(state),
                              ),
                            ],
                          )
                        : Column(
                            children: [
                              SizedBox(
                                height: constraints.maxHeight * 0.38,
                                child: _buildImagePane(state),
                              ),
                              const Divider(height: 1),
                              Expanded(
                                child: _buildObservationsList(state),
                              ),
                            ],
                          ),
                  ),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Theme.of(context).cardColor,
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black12,
                          blurRadius: 4,
                          offset: const Offset(0, -2),
                        ),
                      ],
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '${state.observations.length} Observations',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        if (state.status != 'confirmed')
                          FilledButton.icon(
                            icon: state.isConfirming
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : const Icon(Icons.check),
                            label: const Text('Confirm all'),
                            onPressed: state.isConfirming
                                ? null
                                : () async {
                                    final ok = await ref
                                        .read(
                                          reviewControllerProvider(widget.documentId)
                                              .notifier,
                                        )
                                        .confirmAll();
                                    if (ok && mounted) {
                                      ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(
                                          content: Text('All observations confirmed!'),
                                          backgroundColor: Colors.green,
                                        ),
                                      );
                                    }
                                  },
                          )
                        else
                          const Chip(
                            avatar: Icon(Icons.check_circle, color: Colors.green, size: 18),
                            label: Text('Confirmed'),
                          ),
                      ],
                    ),
                  ),
                ],
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('Error loading review: $err'),
              const SizedBox(height: 8),
              FilledButton(
                onPressed: () => ref.refresh(reviewControllerProvider(widget.documentId)),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
