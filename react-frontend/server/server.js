const express = require('express');
const cors = require('cors');
const { Pool } = require('pg');
const axios = require('axios');
const winston = require('winston');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;

// Logger konfigurieren
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: { service: 'transcript-control-server' },
  transports: [
    new winston.transports.File({ filename: 'error.log', level: 'error' }),
    new winston.transports.File({ filename: 'combined.log' }),
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ],
});

// PostgreSQL Connection Pool
const pool = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  port: process.env.POSTGRES_PORT || 5432,
  database: process.env.POSTGRES_DB || 'transcript_db',
  user: process.env.POSTGRES_USER || 'postgres',
  password: process.env.POSTGRES_PASSWORD || 'password',
  min: 1,
  max: 10,
});

// Middleware
app.use(cors());
app.use(express.json());

// Health Check Endpoint
app.get('/api/health', async (req, res) => {
  try {
    // Database health check
    const dbClient = await pool.connect();
    await dbClient.query('SELECT 1');
    dbClient.release();
    
    // n8n health check
    const n8nUrl = process.env.N8N_URL || 'http://n8n:5678';
    let n8nHealthy = false;
    try {
      // Prüfe ob n8n antwortet (jeder Endpunkt reicht)
      await axios.get(`${n8nUrl}/`, { timeout: 5000 });
      n8nHealthy = true;
    } catch (error) {
      logger.warn('n8n health check failed:', error.message);
    }

    res.json({
      data: {
        database: true,
        n8n: n8nHealthy
      },
      message: 'Health check completed'
    });
  } catch (error) {
    logger.error('Health check failed:', error);
    res.status(500).json({
      data: {
        database: false,
        n8n: false
      },
      error: 'Health check failed'
    });
  }
});

// Get all transcriptions
app.get('/api/transcriptions', async (req, res) => {
  try {
    const { page = 1, limit = 20, search, status, language } = req.query;
    const offset = (page - 1) * limit;
    
    let whereConditions = [];
    let queryParams = [];
    let paramIndex = 1;

    if (search) {
      whereConditions.push(`(filename ILIKE $${paramIndex} OR meeting_title ILIKE $${paramIndex})`);
      queryParams.push(`%${search}%`);
      paramIndex++;
    }

    if (status) {
      whereConditions.push(`transcription_status = $${paramIndex}`);
      queryParams.push(status);
      paramIndex++;
    }

    if (language) {
      whereConditions.push(`set_language = $${paramIndex}`);
      queryParams.push(language);
      paramIndex++;
    }

    const whereClause = whereConditions.length > 0 ? `WHERE ${whereConditions.join(' AND ')}` : '';

    // Count total records
    const countQuery = `SELECT COUNT(*) FROM transcriptions ${whereClause}`;
    const countResult = await pool.query(countQuery, queryParams);
    const total = parseInt(countResult.rows[0].count);

    // Get paginated data
    const dataQuery = `
      SELECT * FROM transcriptions 
      ${whereClause}
      ORDER BY created_at DESC 
      LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
    `;
    queryParams.push(limit, offset);
    
    const dataResult = await pool.query(dataQuery, queryParams);

    res.json({
      data: dataResult.rows,
      total,
      page: parseInt(page),
      limit: parseInt(limit),
      totalPages: Math.ceil(total / limit)
    });
  } catch (error) {
    logger.error('Error fetching transcriptions:', error);
    res.status(500).json({ error: 'Failed to fetch transcriptions' });
  }
});

// Delete multiple transcriptions
app.delete('/api/transcriptions', async (req, res) => {
  const client = await pool.connect();
  try {
    const { ids } = req.body;
    
    if (!ids || !Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ error: 'Invalid IDs provided' });
    }

    await client.query('BEGIN');
    
    const placeholders = ids.map((_, index) => `$${index + 1}`).join(',');
    const deleteQuery = `DELETE FROM transcriptions WHERE id IN (${placeholders})`;
    
    await client.query(deleteQuery, ids);
    await client.query('COMMIT');

    res.json({ data: null, message: `${ids.length} transcriptions deleted successfully` });
  } catch (error) {
    await client.query('ROLLBACK');
    logger.error('Error deleting transcriptions:', error);
    res.status(500).json({ error: 'Failed to delete transcriptions' });
  } finally {
    client.release();
  }
});

// Update transcription language
app.patch('/api/transcriptions/:id/language', async (req, res) => {
  try {
    const { id } = req.params;
    const { language } = req.body;

    if (!language) {
      return res.status(400).json({ error: 'Language is required' });
    }

    const query = 'UPDATE transcriptions SET set_language = $1 WHERE id = $2 RETURNING *';
    const result = await pool.query(query, [language, id]);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Transcription not found' });
    }

    res.json({ data: result.rows[0], message: 'Language updated successfully' });
  } catch (error) {
    logger.error('Error updating transcription language:', error);
    res.status(500).json({ error: 'Failed to update language' });
  }
});

// Link calendar data to transcription
app.post('/api/transcriptions/:id/link-calendar', async (req, res) => {
  const client = await pool.connect();
  try {
    const { id } = req.params;
    const { subject, start_date, end_date, location, attendees } = req.body;

    await client.query('BEGIN');

    // Update transcription with calendar data
    const updateQuery = `
      UPDATE transcriptions 
      SET meeting_title = $1, meeting_start_date = $2, participants = $3
      WHERE id = $4 
      RETURNING *
    `;
    
    const result = await client.query(updateQuery, [
      subject,
      start_date,
      attendees,
      id
    ]);

    if (result.rows.length === 0) {
      await client.query('ROLLBACK');
      return res.status(404).json({ error: 'Transcription not found' });
    }

    await client.query('COMMIT');

    res.json({ 
      data: result.rows[0], 
      message: 'Calendar data linked successfully' 
    });
  } catch (error) {
    await client.query('ROLLBACK');
    logger.error('Error linking calendar data:', error);
    res.status(500).json({ error: 'Failed to link calendar data' });
  } finally {
    client.release();
  }
});

// Get calendar data by date
app.get('/api/calendar', async (req, res) => {
  try {
    const { start_date } = req.query;

    if (!start_date) {
      return res.status(400).json({ error: 'start_date is required' });
    }

    const query = `
      SELECT id, subject, start_date, end_date, location, attendees
      FROM calendar_entries 
      WHERE DATE(start_date) = DATE($1)
      ORDER BY start_date ASC
    `;
    
    const result = await pool.query(query, [start_date]);

    res.json({ data: result.rows });
  } catch (error) {
    logger.error('Error fetching calendar data:', error);
    res.status(500).json({ error: 'Failed to fetch calendar data' });
  }
});

// Get calendar data by day (for meeting dropdown)
app.get('/api/calendar/day', async (req, res) => {
  try {
    const { date } = req.query;

    if (!date) {
      return res.status(400).json({ error: 'date is required (format: YYYY-MM-DD)' });
    }

    logger.info(`Fetching calendar data for date: ${date}`);

    // calendar_data verwendet TIMESTAMPTZ
    // Verwende DATE() Funktion, die automatisch in der Session-Zeitzone arbeitet
    // Kombiniere display_to und display_cc zu attendees
    const query = `
      SELECT 
        id,
        subject,
        start_date,
        end_date,
        has_picture as location,
        COALESCE(
          CASE 
            WHEN display_to IS NOT NULL AND display_cc IS NOT NULL AND display_to != '' AND display_cc != ''
            THEN display_to || '; ' || display_cc
            WHEN display_to IS NOT NULL AND display_to != ''
            THEN display_to
            WHEN display_cc IS NOT NULL AND display_cc != ''
            THEN display_cc
            ELSE NULL
          END,
          ''
        ) as attendees
      FROM calendar_data 
      WHERE DATE(start_date) = $1::date
      ORDER BY start_date ASC
    `;
    
    const result = await pool.query(query, [date]);
    
    logger.info(`Found ${result.rows.length} meetings for date ${date}`);

    res.json({ data: result.rows });
  } catch (error) {
    logger.error('Error fetching calendar data by day:', error);
    res.status(500).json({ error: 'Failed to fetch calendar data by day', details: error.message });
  }
});

// Start workflow
app.post('/api/workflow/start', async (req, res) => {
  try {
    const n8nUrl = process.env.N8N_URL || 'http://n8n:5678';
    const webhookUrl = `${n8nUrl}/webhook/start-transcription`;

    const response = await axios.post(webhookUrl, {}, {
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    res.json({ data: null, message: 'Workflow started successfully' });
  } catch (error) {
    logger.error('Error starting workflow:', error);
    res.status(500).json({ error: 'Failed to start workflow' });
  }
});

// Get workflow status
app.get('/api/workflow/status', async (req, res) => {
  try {
    const n8nUrl = process.env.N8N_URL || 'http://n8n:5678';
    const statusUrl = `${n8nUrl}/api/v1/workflows`;

    const response = await axios.get(statusUrl, {
      timeout: 5000,
      headers: {
        'X-N8N-API-KEY': process.env.N8N_API_KEY || ''
      }
    });

    // Vereinfachte Status-Logik - in der Praxis würde man hier die spezifischen Workflows filtern
    const workflows = response.data.data || [];
    const activeWorkflows = workflows.filter(w => w.active);
    
    res.json({
      data: {
        status: activeWorkflows.length > 0 ? 'active' : 'stopped',
        message: `${activeWorkflows.length} active workflows`
      }
    });
  } catch (error) {
    logger.error('Error fetching workflow status:', error);
    res.status(500).json({ 
      data: { status: 'error', message: 'Failed to fetch workflow status' }
    });
  }
});

// Get column configuration for a table
app.get('/api/table-config/:tableName', async (req, res) => {
  try {
    const { tableName } = req.params;
    
    const query = `
      SELECT column_name, column_width, column_order, is_visible
      FROM react_table_column_config 
      WHERE table_name = $1 
      ORDER BY column_order
    `;
    
    const result = await pool.query(query, [tableName]);
    
    res.json({
      data: result.rows,
      message: `Column configuration loaded for ${tableName}`
    });
  } catch (error) {
    logger.error('Failed to load column configuration:', error);
    res.status(500).json({
      error: 'Failed to load column configuration',
      details: error.message
    });
  }
});

// Update column configuration
app.put('/api/table-config/:tableName', async (req, res) => {
  try {
    const { tableName } = req.params;
    const { columns } = req.body; // Array of { column_name, column_width, column_order, is_visible }
    
    // Begin transaction
    const client = await pool.connect();
    
    try {
      await client.query('BEGIN');
      
      // Update each column configuration
      for (const column of columns) {
        const updateQuery = `
          INSERT INTO react_table_column_config (table_name, column_name, column_width, column_order, is_visible, updated_at)
          VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
          ON CONFLICT (table_name, column_name) 
          DO UPDATE SET
            column_width = EXCLUDED.column_width,
            column_order = EXCLUDED.column_order,
            is_visible = EXCLUDED.is_visible,
            updated_at = CURRENT_TIMESTAMP
        `;
        
        await client.query(updateQuery, [
          tableName,
          column.column_name,
          column.column_width,
          column.column_order,
          column.is_visible
        ]);
      }
      
      await client.query('COMMIT');
      
      res.json({
        message: `Column configuration updated for ${tableName}`,
        data: { updatedColumns: columns.length }
      });
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  } catch (error) {
    logger.error('Failed to update column configuration:', error);
    res.status(500).json({
      error: 'Failed to update column configuration',
      details: error.message
    });
  }
});

// Get transcription setting
app.get('/api/transcription-settings/:parameter', async (req, res) => {
  try {
    const { parameter } = req.params;
    
    const query = 'SELECT parameter, value FROM transcription_settings WHERE parameter = $1';
    const result = await pool.query(query, [parameter]);
    
    if (result.rows.length === 0) {
      return res.json({
        data: { parameter, value: null },
        message: `Setting '${parameter}' not found`
      });
    }
    
    res.json({
      data: result.rows[0],
      message: `Setting '${parameter}' loaded successfully`
    });
  } catch (error) {
    logger.error('Error fetching transcription setting:', error);
    res.status(500).json({ error: 'Failed to fetch transcription setting' });
  }
});

// Get all transcription settings
app.get('/api/transcription-settings', async (req, res) => {
  try {
    const query = 'SELECT parameter, value FROM transcription_settings ORDER BY parameter';
    const result = await pool.query(query);
    
    res.json({
      data: result.rows,
      message: 'All transcription settings loaded successfully'
    });
  } catch (error) {
    logger.error('Error fetching transcription settings:', error);
    res.status(500).json({ error: 'Failed to fetch transcription settings' });
  }
});

// Update transcription setting
app.put('/api/transcription-settings/:parameter', async (req, res) => {
  try {
    const { parameter } = req.params;
    const { value } = req.body;
    
    if (value === undefined) {
      return res.status(400).json({ error: 'value is required' });
    }
    
    const query = `
      INSERT INTO transcription_settings (parameter, value)
      VALUES ($1, $2)
      ON CONFLICT (parameter) DO UPDATE SET value = EXCLUDED.value
      RETURNING parameter, value
    `;
    
    const result = await pool.query(query, [parameter, value]);
    
    res.json({
      data: result.rows[0],
      message: `Setting '${parameter}' updated successfully`
    });
  } catch (error) {
    logger.error('Error updating transcription setting:', error);
    res.status(500).json({ error: 'Failed to update transcription setting' });
  }
});

// Error handling middleware
app.use((error, req, res, next) => {
  logger.error('Unhandled error:', error);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server
app.listen(PORT, () => {
  logger.info(`Server running on port ${PORT}`);
  console.log(`🚀 Server running on http://localhost:${PORT}`);
}); 