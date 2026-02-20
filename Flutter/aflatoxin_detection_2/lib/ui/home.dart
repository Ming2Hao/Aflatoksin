import 'dart:async';
import 'dart:math';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ImageFetcherScreen extends StatefulWidget {
  const ImageFetcherScreen({Key? key}) : super(key: key);

  @override
  State<ImageFetcherScreen> createState() => _ImageFetcherScreenState();
}

class _ImageFetcherScreenState extends State<ImageFetcherScreen> {
  final String baseUrl = 'http://localhost:3000';
  String? imageUrl;
  String? imageUrl2;
  String? finalGrade;
  int? totalObjects;
  double? totalAreaPixels;
  double? totalAreaPercentage;
  double? ppbTotal;
  int? gradingRunId;
  Map<String, dynamic>? summaryByGrade;
  bool isLoading = false;
  bool isHistoryLoading = false;
  List<Map<String, dynamic>> history = [];
  TransformationController controller = TransformationController();
  TapDownDetails? tapDownDetails;

  final TextEditingController _t1Controller = TextEditingController(text: '150');
  final TextEditingController _t2Controller = TextEditingController(text: '160');
  final TextEditingController _t3Controller = TextEditingController(text: '168');

    final TextEditingController _wRejectController =
      TextEditingController(text: '0.00394745');
    final TextEditingController _wGradeDController =
      TextEditingController(text: '0.00615017');
    final TextEditingController _wGradeCController =
      TextEditingController(text: '-0.00570708');

  @override
  void dispose() {
    _t1Controller.dispose();
    _t2Controller.dispose();
    _t3Controller.dispose();
    _wRejectController.dispose();
    _wGradeDController.dispose();
    _wGradeCController.dispose();
    super.dispose();
  }

  List<int>? _getThresholdsOrShowError() {
    final t1 = int.tryParse(_t1Controller.text.trim());
    final t2 = int.tryParse(_t2Controller.text.trim());
    final t3 = int.tryParse(_t3Controller.text.trim());

    if (t1 == null || t2 == null || t3 == null) {
      _showErrorDialog('Semua threshold wajib diisi (angka).');
      return null;
    }

    bool inRange(int v) => v >= 0 && v <= 255;
    if (!inRange(t1) || !inRange(t2) || !inRange(t3)) {
      _showErrorDialog('Threshold harus berada di range 0-255.');
      return null;
    }

    if (!(t1 < t2 && t2 < t3)) {
      _showErrorDialog('Threshold harus lebih besar dari sebelumnya (t1 < t2 < t3).');
      return null;
    }

    return [t1, t2, t3];
  }

  Widget _buildThresholdBox(String label, TextEditingController controller) {
    return TextField(
      controller: controller,
      keyboardType: TextInputType.number,
      inputFormatters: [FilteringTextInputFormatter.digitsOnly],
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    );
  }

  Widget _buildWeightBox(String label, TextEditingController controller) {
    return TextField(
      controller: controller,
      keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true),
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
      ),
    );
  }

  Map<String, double>? _getWeightsOrShowError() {
    double? parse(String s) => double.tryParse(s.trim());

    final wReject = parse(_wRejectController.text);
    final wGradeD = parse(_wGradeDController.text);
    final wGradeC = parse(_wGradeCController.text);

    if (wReject == null || wGradeD == null || wGradeC == null) {
      _showErrorDialog('Semua weight wajib diisi (angka, boleh desimal).');
      return null;
    }

    return {
      'w_reject': wReject,
      'w_grade_d': wGradeD,
      'w_grade_c': wGradeC,
    };
  }

  String _openImageUrl(String path) {
    return '$baseUrl/openImage?image_path=${Uri.encodeComponent(path)}';
  }

  void _applyHistoryItem(Map<String, dynamic> item) {
    final originalPath = item['original_image_path']?.toString();
    final gradedPath = item['graded_image_path']?.toString();
    if (originalPath == null || gradedPath == null) {
      _showErrorDialog('History item has missing image paths');
      return;
    }

    Map<String, dynamic>? summary;
    double? ppbFromHistory;
    final detail = item['detail_json'];
    if (detail != null) {
      try {
        final decoded = detail is String ? json.decode(detail) : detail;
        if (decoded is Map) {
          final decodedMap = decoded.map((k, v) => MapEntry(k.toString(), v));

          final sbg = decodedMap['summary_by_grade'];
          if (sbg is Map) {
            summary = sbg.map((k, v) => MapEntry(k.toString(), v));
          } else {
            summary = decodedMap;
          }

          final ppbVal = decodedMap['ppb_total'];
          if (ppbVal is num) {
            ppbFromHistory = ppbVal.toDouble();
          }

          for (final grade in ['REJECT', 'GRADE D', 'GRADE C']) {
            final gradeData = summary[grade];
            if (gradeData is Map) {
              gradeData.putIfAbsent('objects', () => []);
              summary[grade] = Map<String, dynamic>.from(gradeData);
            }
          }
        }
      } catch (_) {
        summary = null;
      }
    }

    setState(() {
      imageUrl = _openImageUrl(gradedPath);
      imageUrl2 = _openImageUrl(originalPath);
      finalGrade = item['final_grade']?.toString();
      totalObjects = (item['total_objects'] as num?)?.toInt();
      totalAreaPixels = (item['total_area_pixels'] as num?)?.toDouble();
      totalAreaPercentage = (item['total_area_percentage'] as num?)?.toDouble();
      gradingRunId = (item['id'] as num?)?.toInt();
      summaryByGrade = summary;
      ppbTotal = ppbFromHistory ?? _computePpbTotal(summary);
      isLoading = false;
    });
  }

  double? _computePpbTotal(Map<String, dynamic>? summary) {
    if (summary == null) return null;
    double total = 0.0;
    bool any = false;
    for (final grade in ['REJECT', 'GRADE D', 'GRADE C']) {
      final gradeData = summary[grade];
      if (gradeData is Map) {
        final objects = gradeData['objects'];
        if (objects is List) {
          for (final obj in objects) {
            if (obj is Map) {
              final v = obj['ppb'];
              if (v is num) {
                total += v.toDouble();
                any = true;
              }
            }
          }
        }
      }
    }
    return any ? total : null;
  }

  Future<void> fetchImage() async {
    final thresholds = _getThresholdsOrShowError();
    if (thresholds == null) return;

    final weights = _getWeightsOrShowError();
    if (weights == null) return;

    setState(() {
      isLoading = true;
    });

    try {
      Map<String, String> requestHeaders = {
        'X-Api-Key': 'SQpc7nYGBjIPBiHI47Ezjw==M6Fmfih2Z7KZVkOs',
        'Accept': 'image/jpg',
      };
      final uri = Uri.parse('$baseUrl/captureImage2').replace(
        queryParameters: {
          't1': thresholds[0].toString(),
          't2': thresholds[1].toString(),
          't3': thresholds[2].toString(),
          'w_reject': weights['w_reject']!.toString(),
          'w_grade_d': weights['w_grade_d']!.toString(),
          'w_grade_c': weights['w_grade_c']!.toString(),
        },
      );
      final response = await http.get(uri, headers: requestHeaders);

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        print(data);
        if (data is Map && data["error"] != null) {
          setState(() {
            isLoading = false;
          });
          _showErrorDialog(data["error"].toString());
          return;
        }
        print("http://localhost:3000/openImage?image_path=" +
            data["original_image_path"].toString());
        setState(() {
          imageUrl = _openImageUrl(data["graded_image_path"].toString());
          imageUrl2 = _openImageUrl(data["original_image_path"].toString());
          finalGrade = data["final_grade"].toString();
          totalObjects = data["total_objects"] as int?;
          totalAreaPixels = (data["total_area_pixels"] as num?)?.toDouble();
          totalAreaPercentage =
              (data["total_area_percentage"] as num?)?.toDouble();
          gradingRunId = (data["grading_run_id"] as num?)?.toInt();
          summaryByGrade = data["summary_by_grade"] as Map<String, dynamic>?;
          ppbTotal = (data["ppb_total"] as num?)?.toDouble() ??
              _computePpbTotal(summaryByGrade);
          isLoading = false;
        });
      } else {
        setState(() {
          imageUrl = null;
          imageUrl2 = null;
          isLoading = false;
        });
        _showErrorDialog('Failed to load image');
      }
    } catch (e) {
      setState(() {
        imageUrl = null;
        imageUrl2 = null;
        isLoading = false;
      });
      _showErrorDialog('Error: $e');
    }
  }

  void _showErrorDialog(String message) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Error'),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  Future<void> fetchHistory() async {
    setState(() {
      isHistoryLoading = true;
    });

    try {
      final response = await http.get(Uri.parse('$baseUrl/gradingHistory?limit=10'));
      if (response.statusCode != 200) {
        setState(() {
          isHistoryLoading = false;
        });
        try {
          final err = json.decode(response.body);
          if (err is Map && err['detail'] != null) {
            _showErrorDialog(err['detail'].toString());
          } else {
            _showErrorDialog('Failed to load history');
          }
        } catch (_) {
          _showErrorDialog('Failed to load history');
        }
        return;
      }

      final decoded = json.decode(response.body);
      final list = (decoded is Map ? decoded['data'] : null);
      if (list is! List) {
        setState(() {
          isHistoryLoading = false;
        });
        _showErrorDialog('Invalid history response');
        return;
      }

      setState(() {
        history = list
            .whereType<Map>()
            .map((e) => e.map((k, v) => MapEntry(k.toString(), v)))
            .map((e) => Map<String, dynamic>.from(e))
            .toList();
        isHistoryLoading = false;
      });
    } catch (e) {
      setState(() {
        isHistoryLoading = false;
      });
      _showErrorDialog('Error: $e');
    }
  }

  final double aspectRatio = 16 / 9;
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Deteksi Aflatoksin'),
      ),
      body: SingleChildScrollView(
        child: Center(
          child: Container(
            margin: const EdgeInsets.only(top: 15),
            width: min(MediaQuery.of(context).size.width, 900),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  margin: EdgeInsets.only(
                      bottom: MediaQuery.of(context).size.width * 0.01),
                  child: Card(
                      elevation: 10,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(15),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 15, vertical: 15),
                        child: Column(
                          children: [
                            const Padding(
                              padding: EdgeInsets.only(bottom: 15),
                              child: Text(
                                'Deteksi Aflatoksin',
                                style: TextStyle(
                                  fontSize: 20,
                                  fontWeight: FontWeight.bold,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                            const Padding(
                              padding: EdgeInsets.only(bottom: 15),
                              child: Text(
                                'Klik tombol di bawah untuk mengambil gambar dan mendeteksi aflatoksin',
                                style: TextStyle(
                                  fontSize: 16,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.only(bottom: 15),
                              child: Column(
                                children: [
                                  _buildThresholdBox('Batas atas REJECT', _t1Controller),
                                  const SizedBox(height: 10),
                                  _buildThresholdBox('Batas atas GRADE D', _t2Controller),
                                  const SizedBox(height: 10),
                                  _buildThresholdBox('Batas atas GRADE C', _t3Controller),
                                  const SizedBox(height: 16),
                                  _buildWeightBox('Weight REJECT (w_reject)', _wRejectController),
                                  const SizedBox(height: 10),
                                  _buildWeightBox('Weight GRADE D (w_grade_d)', _wGradeDController),
                                  const SizedBox(height: 10),
                                  _buildWeightBox('Weight GRADE C (w_grade_c)', _wGradeCController),
                                ],
                              ),
                            ),
                            ElevatedButton(
                              onPressed: isLoading ? null : fetchImage,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.pink,
                                textStyle: const TextStyle(
                                  color: Colors.white,
                                ),
                                padding: const EdgeInsets.all(25),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(30),
                                ),
                              ),
                              child: Text(
                                  isLoading ? 'Loading...' : 'Fetch Image'),
                            ),
                            const SizedBox(height: 10),
                            ElevatedButton(
                              onPressed: isHistoryLoading ? null : fetchHistory,
                              style: ElevatedButton.styleFrom(
                                padding: const EdgeInsets.all(18),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(30),
                                ),
                              ),
                              child: Text(isHistoryLoading
                                  ? 'Loading History...'
                                  : 'Load History'),
                            ),
                          ],
                        ),
                      )),
                ),
                if (history.isNotEmpty)
                  Card(
                    margin: const EdgeInsets.only(bottom: 20),
                    elevation: 10,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(15),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 15, vertical: 15),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const Text(
                            'History',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 10),
                          ListView.separated(
                            shrinkWrap: true,
                            physics: const NeverScrollableScrollPhysics(),
                            itemCount: history.length,
                            separatorBuilder: (_, __) => const Divider(),
                            itemBuilder: (context, index) {
                              final item = history[index];
                              final capturedAt = item['captured_at']?.toString() ?? '';
                              final grade = item['final_grade']?.toString() ?? '';

                              return InkWell(
                                onTap: () => _applyHistoryItem(item),
                                child: Padding(
                                  padding: const EdgeInsets.symmetric(vertical: 6),
                                  child: Row(
                                    children: [
                                      Expanded(
                                        child: Text(
                                          '$capturedAt  |  $grade',
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                      const Icon(Icons.chevron_right),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
                        ],
                      ),
                    ),
                  ),
                Builder(builder: (context) {
                  if (isLoading) {
                    return const Center(
                      child: SizedBox(
                        width: 50,
                        height: 50,
                        child: CircularProgressIndicator(),
                      ),
                    );
                  } else if (imageUrl != null && imageUrl2 != null) {
                    return Card(
                        margin: const EdgeInsets.only(bottom: 30),
                        elevation: 10,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(15),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 15, vertical: 20),
                          child: Column(
                            children: [
                              Padding(
                                padding: const EdgeInsets.all(15),
                                child: AspectRatio(
                                  aspectRatio: aspectRatio,
                                  child: GestureDetector(
                                    onDoubleTapDown: (details) =>
                                        tapDownDetails = details,
                                    onDoubleTap: () {
                                      final position =
                                          tapDownDetails!.localPosition;

                                      final double scale = 3.0;
                                      final x = -position.dx * (scale - 1);
                                      final y = -position.dy * (scale - 1);
                                      final zoomed = Matrix4.identity()
                                        ..translate(x, y)
                                        ..scale(scale);

                                      final value =
                                          controller.value.isIdentity()
                                              ? zoomed
                                              : Matrix4.identity();
                                      controller.value = value;
                                    },
                                    child: InteractiveViewer(
                                      transformationController: controller,
                                      panEnabled: false,
                                      scaleEnabled: false,
                                      child: Image.network(
                                        fit: BoxFit.fill,
                                        imageUrl!,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                              Padding(
                                padding: const EdgeInsets.all(15),
                                child: AspectRatio(
                                  aspectRatio: aspectRatio,
                                  child: GestureDetector(
                                    onDoubleTapDown: (details) =>
                                        tapDownDetails = details,
                                    onDoubleTap: () {
                                      final position =
                                          tapDownDetails!.localPosition;

                                      final double scale = 3.0;
                                      final x = -position.dx * (scale - 1);
                                      final y = -position.dy * (scale - 1);
                                      final zoomed = Matrix4.identity()
                                        ..translate(x, y)
                                        ..scale(scale);

                                      final value =
                                          controller.value.isIdentity()
                                              ? zoomed
                                              : Matrix4.identity();
                                      controller.value = value;
                                    },
                                    child: InteractiveViewer(
                                      transformationController: controller,
                                      panEnabled: false,
                                      scaleEnabled: false,
                                      child: Image.network(
                                        fit: BoxFit.fill,
                                        imageUrl2!,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                              Padding(
                                padding:
                                    const EdgeInsets.fromLTRB(15, 0, 15, 15),
                                child: Container(
                                  width: double.infinity,
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(15),
                                    color: Colors.grey[200],
                                  ),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 30, vertical: 15),
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Container(
                                          width: double.infinity,
                                          padding: const EdgeInsets.all(15),
                                          margin:
                                              const EdgeInsets.only(bottom: 15),
                                          decoration: BoxDecoration(
                                            borderRadius:
                                                BorderRadius.circular(10),
                                            color: _getGradeColor(finalGrade),
                                          ),
                                          child: Column(
                                            children: [
                                              const Text(
                                                'FINAL GRADE',
                                                style: TextStyle(
                                                  fontSize: 14,
                                                  fontWeight: FontWeight.bold,
                                                  color: Colors.white,
                                                ),
                                              ),
                                              const SizedBox(height: 5),
                                              Text(
                                                finalGrade ?? 'N/A',
                                                style: const TextStyle(
                                                  fontSize: 24,
                                                  fontWeight: FontWeight.bold,
                                                  color: Colors.white,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                        Table(
                                          border: TableBorder(
                                              horizontalInside: BorderSide(
                                                  color: Colors.grey[300]!)),
                                          children: [
                                            TableRow(children: [
                                              const Padding(
                                                padding: EdgeInsets.all(10),
                                                child: Text(
                                                  'Total Objects:',
                                                  style: TextStyle(
                                                    fontWeight: FontWeight.bold,
                                                    color: Colors.blue,
                                                  ),
                                                ),
                                              ),
                                              Padding(
                                                padding:
                                                    const EdgeInsets.all(10),
                                                child: Text(
                                                    totalObjects?.toString() ??
                                                        "0"),
                                              ),
                                            ]),
                                            TableRow(children: [
                                              const Padding(
                                                padding: EdgeInsets.all(10),
                                                child: Text(
                                                  'Total Area (pixels):',
                                                  style: TextStyle(
                                                    fontWeight: FontWeight.bold,
                                                    color: Colors.blue,
                                                  ),
                                                ),
                                              ),
                                              Padding(
                                                padding:
                                                    const EdgeInsets.all(10),
                                                child: Text(
                                                    '${totalAreaPixels?.toStringAsFixed(2) ?? "0"} px'),
                                              ),
                                            ]),
                                            TableRow(children: [
                                              const Padding(
                                                padding: EdgeInsets.all(10),
                                                child: Text(
                                                  'Total Area (%):',
                                                  style: TextStyle(
                                                    fontWeight: FontWeight.bold,
                                                    color: Colors.blue,
                                                  ),
                                                ),
                                              ),
                                              Padding(
                                                padding:
                                                    const EdgeInsets.all(10),
                                                child: Text(
                                                    '${totalAreaPercentage?.toStringAsFixed(4) ?? "0"}%'),
                                              ),
                                            ]),
                                            TableRow(children: [
                                              const Padding(
                                                padding: EdgeInsets.all(10),
                                                child: Text(
                                                  'Total (ppb):',
                                                  style: TextStyle(
                                                    fontWeight: FontWeight.bold,
                                                    color: Colors.blue,
                                                  ),
                                                ),
                                              ),
                                              Padding(
                                                padding: const EdgeInsets.all(10),
                                                child: Text(
                                                  ppbTotal == null
                                                      ? '0'
                                                      : ppbTotal!.toStringAsFixed(3),
                                                ),
                                              ),
                                            ]),
                                          ],
                                        ),
                                        const SizedBox(height: 20),
                                        const Text(
                                          'Breakdown by Grade:',
                                          style: TextStyle(
                                            fontSize: 16,
                                            fontWeight: FontWeight.bold,
                                            color: Colors.black87,
                                          ),
                                        ),
                                        const SizedBox(height: 10),
                                        _buildGradeBreakdown(
                                            'REJECT', Colors.red),
                                        const SizedBox(height: 10),
                                        _buildGradeBreakdown(
                                            'GRADE D', Colors.orange),
                                        const SizedBox(height: 10),
                                        _buildGradeBreakdown(
                                            'GRADE C', Colors.yellow[700]!),
                                        if (gradingRunId != null) ...[
                                          const SizedBox(height: 20),
                                          Text(
                                            'DB ID: $gradingRunId',
                                            style: TextStyle(
                                              fontSize: 12,
                                              color: Colors.grey[600],
                                              fontStyle: FontStyle.italic,
                                            ),
                                          ),
                                        ],
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ));
                  } else {
                    return const Center(
                      child: Text('No image to display'),
                    );
                  }
                }),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildGradeBreakdown(String grade, Color color) {
    final gradeData = summaryByGrade?[grade] as Map<String, dynamic>?;
    final totalPixels = gradeData?['total_pixels'] ?? 0;
    final totalObjects = gradeData?['total_objects'] ?? 0;
    final objects = gradeData?['objects'] as List? ?? [];

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        color: color.withOpacity(0.1),
        border: Border.all(color: color, width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                grade,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  color: color,
                ),
                child: Text(
                  '$totalObjects objects',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Pixels: $totalPixels',
            style: const TextStyle(fontSize: 12),
          ),
          if (objects.isNotEmpty) ...[
            const SizedBox(height: 8),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              title: const Text(
                'View Objects',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
              ),
              children: objects.map<Widget>((obj) {
                final objMap = obj as Map;
                final objId = objMap['object_id'] ?? 0;
                final objGrade = objMap['grade'] ?? 'N/A';
                final objPixels = objMap['total_pixels'] ?? 0;
                final pixelsPerGrade = objMap['pixels_per_grade'] as Map? ?? {};
                final objPpb = (objMap['ppb'] as num?)?.toDouble();
                final objBrightness = (objMap['mean_brightness'] as num?)?.toDouble();

                return Padding(
                  padding: const EdgeInsets.only(left: 16, bottom: 8),
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(6),
                      color: Colors.white,
                      border: Border.all(color: Colors.grey[300]!),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Object #$objId - $objGrade',
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          'Total Pixels: $objPixels',
                          style: const TextStyle(fontSize: 10),
                        ),
                        if (objPpb != null)
                          Text(
                            'PPB: ${objPpb.toStringAsFixed(3)}',
                            style: const TextStyle(fontSize: 10),
                          ),
                        if (objBrightness != null)
                          Text(
                            'Brightness: ${objBrightness.toStringAsFixed(1)}',
                            style: const TextStyle(fontSize: 10),
                          ),
                        if (pixelsPerGrade.isNotEmpty)
                          Text(
                            'Per Grade: ${pixelsPerGrade.entries.map((e) => '${e.key}: ${e.value}').join(', ')}',
                            style: const TextStyle(fontSize: 10),
                          ),
                      ],
                    ),
                  ),
                );
              }).toList(),
            ),
          ],
        ],
      ),
    );
  }

  Color _getGradeColor(String? grade) {
    if (grade == null) return Colors.grey;
    if (grade.contains('REJECT')) return Colors.red;
    if (grade.contains('GRADE D')) return Colors.orange;
    if (grade.contains('GRADE C')) return Colors.yellow[700]!;
    if (grade.contains('GRADE B')) return Colors.lightGreen;
    if (grade.contains('GRADE A')) return Colors.green;
    return Colors.grey;
  }
}
