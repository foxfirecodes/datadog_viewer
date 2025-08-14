#!/usr/bin/env python3
"""
DataDog Error Viewer - Flask Application
A simple web interface to track and manage DataDog test errors from CSV exports.
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

# Configuration
CSV_FILE = 'errors.csv'
PERSISTENCE_FILE = 'addressed_errors.json'
PAGE_SIZE = 50  # Number of errors to show per page


class ErrorTracker:
    """Manages error data and persistence."""

    def __init__(self, csv_file: str, persistence_file: str):
        self.csv_file = csv_file
        self.persistence_file = persistence_file
        self.errors = []
        self.addressed_errors = self._load_persistence()
        self._load_errors()

    def _load_persistence(self) -> Dict[str, bool]:
        """Load addressed error states from JSON file."""
        try:
            if os.path.exists(self.persistence_file):
                with open(self.persistence_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f'Warning: Could not load persistence file: {e}')
        return {}

    def _save_persistence(self):
        """Save addressed error states to JSON file."""
        try:
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(self.addressed_errors, f, indent=2)
        except IOError as e:
            print(f'Error: Could not save persistence file: {e}')

    def _load_errors(self):
        """Load and parse errors from CSV file."""
        if not os.path.exists(self.csv_file):
            print(f"Warning: CSV file '{self.csv_file}' not found")
            return

        # Dictionary to track errors by ID, keeping the newest timestamp
        error_dict = {}

        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header

                for line_num, row in enumerate(reader, start=2):
                    if len(row) < 2:
                        continue

                    try:
                        # Parse timestamp from first column
                        timestamp_str = row[0]
                        try:
                            # Parse ISO 8601 timestamp
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        except ValueError:
                            print(f'Warning: Could not parse timestamp on line {line_num}: {timestamp_str}')
                            continue

                        # Parse the JSON message
                        message_data = json.loads(row[1])
                        test_info = message_data.get('test', {})
                        error_info = message_data.get('error', {})

                        # Extract error details
                        test_file = test_info.get('source', {}).get('file', 'unknown')
                        test_name = test_info.get('name', 'unknown')
                        error_message = error_info.get('message', '')

                        # Filter out application context errors
                        if 'RuntimeError: Working outside of application context.' in error_message:
                            continue

                        # Create unique identifier for the error
                        error_id = f'{test_file}::{test_name}'

                        # Get first line of error for summary
                        error_summary = error_message.split('\n')[0] if error_message else 'No error message'

                        error_data = {
                            'id': error_id,
                            'file': test_file,
                            'test_name': test_name,
                            'error_summary': error_summary,
                            'error_full': error_message,
                            'addressed': self.addressed_errors.get(error_id, False),
                            'timestamp': timestamp,
                        }

                        # Keep the error with the newest timestamp if there are duplicates
                        if error_id not in error_dict or timestamp > error_dict[error_id]['timestamp']:
                            error_dict[error_id] = error_data

                    except (json.JSONDecodeError, KeyError) as e:
                        print(f'Warning: Could not parse line {line_num}: {e}')
                        continue

        except IOError as e:
            print(f'Error: Could not read CSV file: {e}')

        # Convert dictionary values to list and sort by error ID alphabetically
        self.errors = sorted(error_dict.values(), key=lambda x: x['id'])

    def get_errors(self, page: int = 1) -> Dict:
        """Get paginated errors."""
        start_idx = (page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE

        total_pages = (len(self.errors) + PAGE_SIZE - 1) // PAGE_SIZE

        return {
            'errors': self.errors[start_idx:end_idx],
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_errors': len(self.errors),
                'has_prev': page > 1,
                'has_next': page < total_pages,
            },
        }

    def toggle_error_status(self, error_id: str) -> bool:
        """Toggle the addressed status of an error."""
        if error_id in self.addressed_errors:
            self.addressed_errors[error_id] = not self.addressed_errors[error_id]
        else:
            self.addressed_errors[error_id] = True

        # Update the error in our list
        for error in self.errors:
            if error['id'] == error_id:
                error['addressed'] = self.addressed_errors[error_id]
                break

        self._save_persistence()
        return self.addressed_errors[error_id]

    def get_stats(self) -> Dict:
        """Get error statistics."""
        total = len(self.errors)
        addressed = sum(1 for error in self.errors if error['addressed'])
        unaddressed = total - addressed

        return {
            'total': total,
            'addressed': addressed,
            'unaddressed': unaddressed,
            'progress_percent': round((addressed / total * 100) if total > 0 else 0, 1),
        }


# Initialize error tracker
error_tracker = ErrorTracker(CSV_FILE, PERSISTENCE_FILE)


@app.route('/')
def index():
    """Main page displaying errors."""
    page = request.args.get('page', 1, type=int)
    data = error_tracker.get_errors(page)
    stats = error_tracker.get_stats()

    return render_template_string(HTML_TEMPLATE, errors=data['errors'], pagination=data['pagination'], stats=stats)


@app.route('/api/toggle/<path:error_id>', methods=['POST'])
def toggle_error(error_id):
    """API endpoint to toggle error status."""
    try:
        new_status = error_tracker.toggle_error_status(error_id)
        return jsonify({'success': True, 'error_id': error_id, 'addressed': new_status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stats')
def get_stats():
    """API endpoint to get current statistics."""
    return jsonify(error_tracker.get_stats())


# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataDog Error Viewer</title>
    <script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .stats {
            display: flex;
            justify-content: space-around;
            padding: 20px;
            background: #ecf0f1;
            border-bottom: 1px solid #bdc3c7;
        }
        .stat-item {
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        }
        .stat-label {
            color: #7f8c8d;
            font-size: 14px;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #ecf0f1;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            height: 100%;
            background: #27ae60;
            transition: width 0.3s ease;
        }
        .table-container {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }
        th {
            background: #34495e;
            color: white;
            font-weight: 500;
        }
        tr:hover {
            background-color: #f8f9fa;
        }
        .checkbox-cell {
            width: 50px;
            text-align: center;
        }
        .file-cell {
            width: 300px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
        }
        .test-cell {
            width: 250px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 13px;
        }
        .error-cell {
            min-width: 400px;
        }
        .error-summary {
            cursor: pointer;
            color: #e74c3c;
            font-weight: 500;
        }
        .error-summary:hover {
            text-decoration: underline;
        }
        .error-details {
            display: none;
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 10px;
            margin-top: 10px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            white-space: pre-wrap;
            max-height: 300px;
            overflow-y: auto;
        }
        .error-details.show {
            display: block;
        }
        .addressed {
            background-color: #d5f4e6;
        }
        .addressed .error-summary {
            color: #27ae60;
            text-decoration: line-through;
        }
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            gap: 10px;
        }
        .pagination a, .pagination span {
            padding: 8px 12px;
            text-decoration: none;
            border: 1px solid #ddd;
            color: #333;
            border-radius: 4px;
        }
        .pagination a:hover {
            background-color: #f5f5f5;
        }
        .pagination .current {
            background-color: #007bff;
            color: white;
            border-color: #007bff;
        }
        .pagination .disabled {
            color: #999;
            cursor: not-allowed;
        }
        .checkbox {
            transform: scale(1.2);
            cursor: pointer;
        }
        .loading {
            opacity: 0.5;
            pointer-events: none;
        }
        .search-bar {
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }
        .search-input {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
        }
        .search-input:focus {
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
        }
        .filter-controls {
            display: flex;
            gap: 15px;
            margin-top: 10px;
            align-items: center;
        }
        .filter-select {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            background: white;
        }
        .filter-checkbox {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .filter-checkbox input {
            transform: scale(1.1);
        }
        .clickable {
            cursor: pointer;
        }
        .clickable:hover {
            background-color: #f5f5f5;
        }
    </style>
</head>
<body>
    <div class="container" x-data="errorViewer()">
        <div class="header">
            <h1>DataDog Error Viewer</h1>
            <p>Track and manage test errors from DataDog exports</p>
        </div>

        <div class="stats">
            <div class="stat-item">
                <div class="stat-number" x-text="stats.total"></div>
                <div class="stat-label">Total Errors</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" x-text="stats.addressed"></div>
                <div class="stat-label">Addressed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" x-text="stats.unaddressed"></div>
                <div class="stat-label">Unaddressed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" x-text="stats.progress_percent + '%'"></div>
                <div class="stat-label">Progress</div>
                <div class="progress-bar">
                    <div class="progress-fill" :style="'width: ' + stats.progress_percent + '%'"></div>
                </div>
            </div>
        </div>

        <div class="search-bar">
            <input type="text" 
                   class="search-input" 
                   placeholder="Search errors by file, test name, or error message..."
                   x-model="searchQuery"
                   @input="filterErrors">
            <div class="filter-controls">
                <select class="filter-select" x-model="statusFilter" @change="filterErrors">
                    <option value="all">All Status</option>
                    <option value="addressed">Addressed Only</option>
                    <option value="unaddressed">Unaddressed Only</option>
                </select>
                <div class="filter-checkbox">
                    <input type="checkbox" id="showDetails" @change="toggleAllErrorDetails">
                    <label for="showDetails">Show all error details</label>
                </div>
                <span x-text="'Showing ' + (filteredErrors ? filteredErrors.length : 0) + ' of ' + (allErrors ? allErrors.length : 0) + ' errors'"></span>
            </div>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th class="checkbox-cell">Status</th>
                        <th class="file-cell">File</th>
                        <th class="test-cell">Test Name</th>
                        <th class="error-cell">Error Summary</th>
                    </tr>
                </thead>
                <tbody>
                    <template x-for="error in paginatedErrors" x-key="error.id">
                        <tr :class="{ 'addressed': error.addressed, 'loading': error.loading }" :data-error-id="error.id">
                            <td class="checkbox-cell">
                                <input type="checkbox" class="checkbox"
                                       :checked="error.addressed"
                                       @change="toggleError(error.id, $event.target)">
                            </td>
                            <td class="file-cell" x-text="error.file"></td>
                            <td class="test-cell" x-text="error.test_name"></td>
                            <td class="error-cell">
                                <div class="error-summary" 
                                     @click="toggleErrorDetails(error.id)"
                                     x-text="error.error_summary"></div>
                                <div class="error-details" 
                                     :class="{ 'show': error.showDetails }"
                                     x-text="error.error_full"></div>
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>
        </div>

        <div class="pagination" x-show="totalPages > 1">
            <a href="#" 
               @click.prevent="changePage(currentPage - 1)"
               :class="{ 'disabled': currentPage <= 1 }">&laquo; Previous</a>
            
            <template x-for="pageNum in pageNumbers" x-key="pageNum">
                <span :class="{ 'current': pageNum === currentPage, 'clickable': pageNum !== currentPage }"
                      x-text="pageNum"
                      @click="pageNum !== currentPage && changePage(pageNum)"></span>
            </template>
            
            <a href="#" 
               @click.prevent="changePage(currentPage + 1)"
               :class="{ 'disabled': currentPage >= totalPages }">Next &raquo;</a>
        </div>
    </div>

    <script>
        function errorViewer() {
            return {
                allErrors: [],
                filteredErrors: [],
                searchQuery: '',
                statusFilter: 'all',
                showAllDetails: false,
                currentPage: 1,
                pageSize: 50,
                stats: { total: 0, addressed: 0, unaddressed: 0, progress_percent: 0 },
                
                init() {
                    // Initialize with data from Flask
                    this.allErrors = {{ errors | tojson }};
                    this.stats = {{ stats | tojson }};
                    
                    // Add showDetails property to each error (default: false)
                    this.allErrors.forEach(error => {
                        error.showDetails = false;
                        error.loading = false;
                    });
                    
                    this.filteredErrors = [...this.allErrors];
                },
                
                get paginatedErrors() {
                    if (!this.filteredErrors || this.filteredErrors.length === 0) {
                        return [];
                    }
                    const start = (this.currentPage - 1) * this.pageSize;
                    const end = start + this.pageSize;
                    return this.filteredErrors.slice(start, end);
                },
                
                get totalPages() {
                    if (!this.filteredErrors) return 1;
                    return Math.ceil(this.filteredErrors.length / this.pageSize);
                },
                
                get pageNumbers() {
                    if (!this.filteredErrors) return [];
                    const pages = [];
                    const maxVisible = 7;
                    let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
                    let end = Math.min(this.totalPages, start + maxVisible - 1);
                    
                    if (end - start + 1 < maxVisible) {
                        start = Math.max(1, end - maxVisible + 1);
                    }
                    
                    for (let i = start; i <= end; i++) {
                        pages.push(i);
                    }
                    return pages;
                },
                
                filterErrors() {
                    if (!this.allErrors) return;
                    
                    let filtered = this.allErrors;
                    
                    // Apply search filter
                    if (this.searchQuery.trim()) {
                        const query = this.searchQuery.toLowerCase();
                        filtered = filtered.filter(error => 
                            error.file.toLowerCase().includes(query) ||
                            error.test_name.toLowerCase().includes(query) ||
                            error.error_summary.toLowerCase().includes(query) ||
                            error.error_full.toLowerCase().includes(query)
                        );
                    }
                    
                    // Apply status filter
                    if (this.statusFilter === 'addressed') {
                        filtered = filtered.filter(error => error.addressed);
                    } else if (this.statusFilter === 'unaddressed') {
                        filtered = filtered.filter(error => !error.addressed);
                    }
                    
                    this.filteredErrors = filtered;
                    this.currentPage = 1; // Reset to first page when filtering
                },
                
                changePage(page) {
                    if (page >= 1 && page <= this.totalPages) {
                        this.currentPage = page;
                    }
                },
                
                toggleErrorDetails(errorId) {
                    const error = this.allErrors.find(e => e.id === errorId);
                    if (error) {
                        error.showDetails = !error.showDetails;
                    }
                },
                
                toggleAllErrorDetails() {
                    const checkbox = document.getElementById('showDetails');
                    const showAll = checkbox.checked;
                    
                    this.allErrors.forEach(error => {
                        error.showDetails = showAll;
                    });
                },
                
                async toggleError(errorId, checkbox) {
                    const error = this.allErrors.find(e => e.id === errorId);
                    if (!error) return;
                    
                    error.loading = true;
                    
                    try {
                        const response = await fetch(`/api/toggle/${encodeURIComponent(errorId)}`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            }
                        });
                        
                        const data = await response.json();
                        
                        if (data.success) {
                            error.addressed = data.addressed;
                            this.updateStats();
                        } else {
                            console.error('Error toggling status:', data.error);
                            checkbox.checked = !checkbox.checked; // Revert checkbox
                        }
                    } catch (error) {
                        console.error('Error:', error);
                        checkbox.checked = !checkbox.checked; // Revert checkbox
                    } finally {
                        error.loading = false;
                    }
                },
                
                async updateStats() {
                    try {
                        const response = await fetch('/api/stats');
                        const newStats = await response.json();
                        this.stats = newStats;
                    } catch (error) {
                        console.error('Error updating stats:', error);
                    }
                }
            }
        }
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    print('DataDog Error Viewer')
    print('=' * 30)
    print(f'CSV file: {CSV_FILE}')
    print(f'Persistence file: {PERSISTENCE_FILE}')
    print(f'Total errors loaded: {len(error_tracker.errors)}')
    print(f"Addressed errors: {sum(1 for e in error_tracker.errors if e['addressed'])}")
    print('\nStarting Flask application...')
    print('Open http://localhost:6969 in your browser')

    app.run(debug=True, host='0.0.0.0', port=6969)
