import 'dart:async';
import 'dart:math';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class ImageFetcherScreen extends StatefulWidget {
  const ImageFetcherScreen({Key? key}) : super(key: key);

  @override
  State<ImageFetcherScreen> createState() => _ImageFetcherScreenState();
}

class _ImageFetcherScreenState extends State<ImageFetcherScreen> {
  String? imageUrl;
  String? imageUrl2;
  String? finalGrade;
  int? totalObjects;
  double? totalAreaPixels;
  double? totalAreaPercentage;
  String? csvFilename;
  Map<String, dynamic>? summaryByGrade;
  bool isLoading = false;
  TransformationController controller = TransformationController();
  TapDownDetails? tapDownDetails;

  Future<void> fetchImage() async {
    setState(() {
      isLoading = true;
    });

    try {
      // Using Unsplash API as an example
      // Replace with your preferred image API endpoint
      Map<String, String> requestHeaders = {
        'X-Api-Key': 'SQpc7nYGBjIPBiHI47Ezjw==M6Fmfih2Z7KZVkOs',
        'Accept': 'image/jpg',
      };
      final response = await http.get(
          Uri.parse('http://localhost:3000/captureImage2'),
          headers: requestHeaders);

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        print(data);
        print("http://localhost:3000/openImage?image_path=" +
            data["original_image_path"].toString());
        setState(() {
          imageUrl = "http://localhost:3000/openImage?image_path=" +
              data["graded_image_path"].toString();
          imageUrl2 = "http://localhost:3000/openImage?image_path=" +
              data["original_image_path"].toString();
          finalGrade = data["final_grade"].toString();
          totalObjects = data["total_objects"] as int?;
          totalAreaPixels = (data["total_area_pixels"] as num?)?.toDouble();
          totalAreaPercentage =
              (data["total_area_percentage"] as num?)?.toDouble();
          csvFilename = data["csv_filename"]?.toString();
          summaryByGrade = data["summary_by_grade"] as Map<String, dynamic>?;
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
                          ],
                        ),
                      )),
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
                                      // Handle double tap if needed
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
                                      // clipBehavior: Clip.none,
                                      transformationController: controller,
                                      panEnabled: false,
                                      scaleEnabled: false,
                                      child: Image.network(
                                        fit: BoxFit.fill,
                                        imageUrl!,
                                        // loadingBuilder: (context, child, loadingProgress) {
                                        //   if (loadingProgress == null) return child;
                                        //   return Center(
                                        //     child: CircularProgressIndicator(
                                        //       value: loadingProgress.expectedTotalBytes != null
                                        //           ? loadingProgress.cumulativeBytesLoaded /
                                        //               loadingProgress.expectedTotalBytes!
                                        //           : null,
                                        //     ),
                                        //   );
                                        // },
                                        // errorBuilder: (context, error, stackTrace) {
                                        //   return const Center(
                                        //     child: Text('Failed to load image'),
                                        //   );
                                        // },
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
                                      // Handle double tap if needed
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
                                      // clipBehavior: Clip.none,
                                      transformationController: controller,
                                      panEnabled: false,
                                      scaleEnabled: false,
                                      child: Image.network(
                                        fit: BoxFit.fill,
                                        imageUrl2!,
                                        // loadingBuilder: (context, child, loadingProgress) {
                                        //   if (loadingProgress == null) return child;
                                        //   return Center(
                                        //     child: CircularProgressIndicator(
                                        //       value: loadingProgress.expectedTotalBytes != null
                                        //           ? loadingProgress.cumulativeBytesLoaded /
                                        //               loadingProgress.expectedTotalBytes!
                                        //           : null,
                                        //     ),
                                        //   );
                                        // },
                                        // errorBuilder: (context, error, stackTrace) {
                                        //   return const Center(
                                        //     child: Text('Failed to load image'),
                                        //   );
                                        // },
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
                                        // Final Grade - Highlighted
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
                                        // Total Statistics
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
                                          ],
                                        ),
                                        const SizedBox(height: 20),
                                        // Grade Breakdown
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
                                        if (csvFilename != null) ...[
                                          const SizedBox(height: 20),
                                          Text(
                                            'CSV File: $csvFilename',
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
