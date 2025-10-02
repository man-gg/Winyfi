# PDF Generation Functionality

This document describes the PDF generation functionality that has been added to the Network Monitoring System for both admin and client interfaces.

## Overview

The PDF functionality allows users to generate professional reports in PDF format with the following features:
- Summary statistics
- Detailed data tables
- Charts and graphs (in charts version)
- Professional formatting
- Automatic file naming based on date range

## Server Endpoints

### 1. Basic PDF Report
- **Endpoint**: `GET /api/reports/pdf`
- **Parameters**:
  - `start_date` (required): Start date in YYYY-MM-DD format
  - `end_date` (required): End date in YYYY-MM-DD format
  - `mode` (optional): View mode (daily, weekly, monthly) - defaults to "weekly"

**Example**:
```
GET /api/reports/pdf?start_date=2024-01-01&end_date=2024-01-07&mode=weekly
```

### 2. PDF Report with Charts
- **Endpoint**: `GET /api/reports/pdf-with-charts`
- **Parameters**: Same as basic PDF report
- **Features**: Includes uptime trend charts

**Example**:
```
GET /api/reports/pdf-with-charts?start_date=2024-01-01&end_date=2024-01-07&mode=weekly
```

## Client Interface

### Reports Tab Features

The client reports tab now includes two PDF generation buttons:

1. **🖨️ Print PDF** - Generates a basic PDF report with:
   - Report title and generation date
   - Summary statistics table
   - Detailed router data table
   - Professional formatting

2. **📈 PDF with Charts** - Generates a PDF report with:
   - All features of basic PDF
   - Uptime trend chart
   - Visual data representation

### Usage Instructions

1. **Set Date Range**: Use the date picker controls to select your desired date range
2. **Choose View Mode**: Select daily, weekly, or monthly view mode
3. **Generate Report**: Click "📊 Generate Report" to load data
4. **Export PDF**: 
   - Click "🖨️ Print PDF" for basic report
   - Click "📈 PDF with Charts" for report with visual charts
5. **Save File**: Choose where to save the PDF file
6. **View Report**: The PDF will automatically open in your default PDF viewer

## Dependencies

The PDF functionality requires the following Python packages:

```
reportlab==4.0.4
matplotlib==3.7.2
```

Install with:
```bash
pip install reportlab matplotlib
```

## File Structure

```
server/
├── app.py                 # Contains PDF endpoints
client_window/tabs/
├── reports_tab.py         # Contains PDF generation UI
test_pdf_endpoints.py      # Test script for PDF endpoints
requirements.txt           # Python dependencies
```

## Testing

Use the provided test script to verify PDF generation:

```bash
python test_pdf_endpoints.py
```

This will:
1. Test both PDF endpoints
2. Generate sample PDF files
3. Display success/error messages
4. Show file sizes

## PDF Content

### Basic PDF Report Contains:
- **Header**: Report title and generation timestamp
- **Report Info**: Date range and view mode
- **Summary Section**: 
  - Total routers count
  - Average uptime percentage
  - Total bandwidth usage
- **Detailed Report Table**:
  - Router name
  - Start date
  - Uptime percentage
  - Downtime duration
  - Bandwidth usage

### PDF with Charts Contains:
- All content from basic PDF
- **Uptime Trend Chart**: Line graph showing uptime trends over time
- **Visual Data**: Professional chart formatting

## Error Handling

The system includes comprehensive error handling for:
- Invalid date formats
- Date range validation
- Server connection issues
- PDF generation failures
- File save errors

## Future Enhancements

Potential improvements for future versions:
- Multiple chart types (bar charts, pie charts)
- Custom report templates
- Email integration for automatic report delivery
- Scheduled report generation
- Advanced filtering options
- Custom branding and logos

## Troubleshooting

### Common Issues:

1. **"Failed to connect to server"**
   - Ensure the server is running on port 5000
   - Check network connectivity

2. **"PDF generation failed"**
   - Verify all dependencies are installed
   - Check server logs for detailed error messages

3. **"Chart generation failed"**
   - Ensure matplotlib is properly installed
   - Check that the server has write permissions for temporary files

4. **Empty PDF files**
   - Verify database connection
   - Check that router data exists for the selected date range

## Support

For technical support or feature requests, please refer to the main project documentation or contact the development team.

