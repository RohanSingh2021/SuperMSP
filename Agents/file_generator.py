"""
File generator module for creating PDF exports of analysis results.
"""
import os
import json
import re
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class FileGenerator:
    """Handles generation of PDF files from analysis results."""
    
    def __init__(self, output_dir="exports", max_files=10):
        """
        Initialize file generator.
        
        Args:
            output_dir: Directory to store exported files
            max_files: Maximum number of files to keep in the directory
        """
        self.output_dir = output_dir
        self.max_files = max_files
        os.makedirs(output_dir, exist_ok=True)
    
    
    def _cleanup_old_files(self):
        """
        Remove oldest files if directory exceeds max_files limit.
        Files are sorted by modification time, oldest first.
        """
        try:
            files = []
            for filename in os.listdir(self.output_dir):
                filepath = os.path.join(self.output_dir, filename)
                if os.path.isfile(filepath) and not filename.startswith('.'):
                    files.append(filepath)
            
            if len(files) >= self.max_files:
                files.sort(key=lambda x: os.path.getmtime(x))
                
                files_to_remove = len(files) - self.max_files + 1
                
                for i in range(files_to_remove):
                    try:
                        os.remove(files[i])
                        print(f"Removed old file: {os.path.basename(files[i])}")
                    except OSError as e:
                        print(f"Warning: Could not remove file {files[i]}: {e}")
                        
        except Exception as e:
            print(f"Warning: Error during cleanup: {e}")
    
    def _generate_filename(self, extension, query):
        """Generate timestamped filename."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c for c in query[:30] if c.isalnum() or c in (' ', '_')).strip()
        safe_query = safe_query.replace(' ', '_')
        filename = f"msp_analysis_{safe_query}_{timestamp}.{extension}"
        return os.path.join(self.output_dir, filename)
    
    def generate_pdf(self, user_query, analysis_result, include_agent_details=True):
        """
        Generate PDF report from analysis results.
        
        Args:
            user_query: Original user query
            analysis_result: Dict containing analysis data
            include_agent_details: Whether to include detailed agent responses in PDF
        
        Returns:
            str: Path to generated PDF file
        """
        self._cleanup_old_files()
        
        filepath = self._generate_filename("pdf", user_query)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter,
                              rightMargin=72, leftMargin=72,
                              topMargin=72, bottomMargin=18)
        
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        title = Paragraph("MSP Analysis Report", title_style)
        elements.append(title)
        elements.append(Spacer(1, 0.2*inch))
        
        metadata = [
            ['Query:', user_query],
            ['Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ['Complexity:', analysis_result.get('complexity', 'N/A').upper()],
            ['Agents Used:', ', '.join(analysis_result.get('agents', []))]
        ]
        
        metadata_table = Table(metadata, colWidths=[1.5*inch, 5*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 0.3*inch))
        
        elements.append(Paragraph("Analysis Results", heading_style))
        response_text = analysis_result.get('final_response', 'No response generated')
        response_para = Paragraph(response_text.replace('\n', '<br/>'), styles['Normal'])
        elements.append(response_para)
        elements.append(Spacer(1, 0.3*inch))
        
        agent_results = analysis_result.get('agent_results', {})
        if agent_results and include_agent_details:
            elements.append(PageBreak())
            elements.append(Paragraph("Detailed Agent Data", heading_style))
            elements.append(Spacer(1, 0.2*inch))
            
            for agent_name, result in agent_results.items():
                agent_title = agent_name.replace('_', ' ').title()
                elements.append(Paragraph(f"<b>{agent_title}</b>", styles['Heading3']))
                
                if isinstance(result, (dict, list)):
                    result_text = json.dumps(result, indent=2)
                else:
                    result_text = str(result)
                
                if len(result_text) > 10000:
                    result_text = result_text[:10000] + "\n... (truncated)"
                
                result_para = Paragraph(f"<pre>{result_text}</pre>", styles['Code'])
                elements.append(result_para)
                elements.append(Spacer(1, 0.2*inch))
        
        doc.build(elements)
        return filepath
    
def generate_file(user_query, analysis_result, file_type, include_agent_details=True):
    """
    Convenience function to generate file of specified type.
    
    Args:
        user_query: Original user query
        analysis_result: Dict containing analysis data
        file_type: 'pdf'
        include_agent_details: Whether to include detailed agent responses in the file
    
    Returns:
        str: Path to generated file
    """
    generator = FileGenerator()
    
    if file_type.lower() == 'pdf':
        return generator.generate_pdf(user_query, analysis_result, include_agent_details)
    else:
        raise ValueError(f"Unsupported file type: {file_type}. Only 'pdf' is supported.")
