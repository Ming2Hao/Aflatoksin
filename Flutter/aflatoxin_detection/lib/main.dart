import 'dart:math';

import 'package:aflatoxin_detection/ui/home.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Deteksi Aflatoksin',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      home: const ImageFetcherScreen(),
    );
  }
}
