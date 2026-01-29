"""
UK Mobility Dashboard - Plotly/Dash Application

Interactive visualization of transport ridership trends.
"""

import os
from datetime import date, datetime, timedelta
from typing import List, Optional

import dash
from dash import dcc, html, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from ..database import get_session, get_engine, TransportJourney, BaselineData
from ..fetchers import TfLDataFetcher


# Mode display names and colors
MODE_CONFIG = {
    'tube': {'name': 'London Underground', 'color': '#003688'},
    'bus': {'name': 'London Buses', 'color': '#DC241F'},
    'dlr': {'name': 'DLR', 'color': '#00A4A7'},
    'overground': {'name': 'London Overground', 'color': '#EE7C0E'},
    'tram': {'name': 'Tramlink', 'color': '#84B817'},
    'cable_car': {'name': 'Emirates Air Line', 'color': '#E21836'},
    'elizabeth_line': {'name': 'Elizabeth Line', 'color': '#6950A1'},
}


def create_app(db_path: Optional[str] = None) -> dash.Dash:
    """Create and configure the Dash application."""

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.FLATLY],
        title='UK Mobility Dashboard',
        suppress_callback_exceptions=True,
    )

    # Store database path
    app.db_path = db_path

    # Layout
    app.layout = dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H1("UK Mobility Dashboard", className="mt-4 mb-2"),
                html.P(
                    "Transport ridership trends across London (TfL data)",
                    className="text-muted mb-4"
                ),
            ])
        ]),

        # Controls row
        dbc.Row([
            # Mode selector
            dbc.Col([
                html.Label("Transport Modes", className="fw-bold"),
                dcc.Dropdown(
                    id='mode-selector',
                    options=[
                        {'label': cfg['name'], 'value': mode}
                        for mode, cfg in MODE_CONFIG.items()
                    ],
                    value=['tube', 'bus', 'dlr', 'overground'],
                    multi=True,
                    placeholder="Select transport modes..."
                ),
            ], md=4),

            # View type toggle
            dbc.Col([
                html.Label("View Type", className="fw-bold"),
                dbc.RadioItems(
                    id='view-type',
                    options=[
                        {'label': 'Absolute (millions)', 'value': 'absolute'},
                        {'label': 'Indexed (100 = 2019)', 'value': 'indexed'},
                    ],
                    value='absolute',
                    inline=True,
                ),
            ], md=3),

            # Aggregation selector
            dbc.Col([
                html.Label("Aggregation", className="fw-bold"),
                dbc.RadioItems(
                    id='aggregation',
                    options=[
                        {'label': 'Period', 'value': 'period'},
                        {'label': 'Monthly', 'value': 'monthly'},
                        {'label': 'Quarterly', 'value': 'quarterly'},
                    ],
                    value='period',
                    inline=True,
                ),
            ], md=3),

            # Rolling average toggle
            dbc.Col([
                html.Label("Smoothing", className="fw-bold"),
                dbc.Checklist(
                    id='smoothing-toggle',
                    options=[{'label': '3-period rolling avg', 'value': 'rolling'}],
                    value=[],
                    inline=True,
                ),
            ], md=2),
        ], className="mb-3"),

        # Date range selector
        dbc.Row([
            dbc.Col([
                html.Label("Date Range", className="fw-bold"),
                dcc.DatePickerRange(
                    id='date-range',
                    min_date_allowed=date(2019, 1, 1),
                    max_date_allowed=date.today(),
                    start_date=date(2022, 1, 1),
                    end_date=date.today(),
                    display_format='MMM YYYY',
                ),
            ], md=6),

            # Quick date range buttons
            dbc.Col([
                html.Label("Quick Select", className="fw-bold"),
                dbc.ButtonGroup([
                    dbc.Button("2019", id="btn-2019", size="sm", outline=True, color="secondary"),
                    dbc.Button("2022+", id="btn-2022", size="sm", outline=True, color="secondary"),
                    dbc.Button("Last Year", id="btn-1y", size="sm", outline=True, color="secondary"),
                    dbc.Button("All Time", id="btn-all", size="sm", outline=True, color="secondary"),
                ]),
            ], md=6),
        ], className="mb-4"),

        # Main chart
        dbc.Row([
            dbc.Col([
                dcc.Loading(
                    id="loading-chart",
                    type="default",
                    children=[
                        dcc.Graph(
                            id='main-chart',
                            config={
                                'displayModeBar': True,
                                'toImageButtonOptions': {
                                    'format': 'png',
                                    'filename': 'uk_mobility_chart',
                                    'height': 600,
                                    'width': 1200,
                                    'scale': 2
                                }
                            },
                            style={'height': '500px'}
                        ),
                    ]
                ),
            ])
        ]),

        # Summary statistics
        dbc.Row([
            dbc.Col([
                html.H5("Summary Statistics", className="mt-4 mb-3"),
                html.Div(id='summary-stats'),
            ])
        ]),

        # Export section
        dbc.Row([
            dbc.Col([
                html.Hr(),
                dbc.Button(
                    "Export to CSV",
                    id="btn-export",
                    color="primary",
                    className="me-2"
                ),
                dcc.Download(id="download-csv"),
                html.Span(id="export-status", className="text-muted ms-2"),
            ])
        ], className="mt-4 mb-4"),

        # Data management section
        dbc.Row([
            dbc.Col([
                html.Hr(),
                html.H5("Data Management", className="mb-3"),
                dbc.Button(
                    "Load Sample Data",
                    id="btn-load-sample",
                    color="secondary",
                    outline=True,
                    className="me-2"
                ),
                dcc.Upload(
                    id='upload-csv',
                    children=dbc.Button(
                        "Upload TfL CSV",
                        color="secondary",
                        outline=True,
                    ),
                    multiple=False,
                    accept='.csv'
                ),
                html.Div(id="data-status", className="mt-2"),
            ])
        ], className="mb-4"),

        # Hidden store for data refresh
        dcc.Store(id='data-refresh-trigger', data=0),

        # Footer
        dbc.Row([
            dbc.Col([
                html.Hr(),
                html.P([
                    "Data source: ",
                    html.A(
                        "Transport for London via London Datastore",
                        href="https://data.london.gov.uk/dataset/public-transport-journeys-type-transport/",
                        target="_blank"
                    ),
                    " | Phase 1 of UK Mobility Dashboard"
                ], className="text-muted small"),
            ])
        ]),

    ], fluid=True)

    # Register callbacks
    register_callbacks(app)

    return app


def get_data(
    db_path: Optional[str],
    start_date: date,
    end_date: date,
    modes: List[str],
    aggregation: str = 'period'
) -> pd.DataFrame:
    """Fetch data from database."""
    fetcher = TfLDataFetcher(db_path)
    df = fetcher.get_journey_data(
        start_date=start_date,
        end_date=end_date,
        modes=modes,
    )

    if df.empty:
        return df

    # Ensure date column is datetime
    df['date'] = pd.to_datetime(df['date'])

    # Apply aggregation
    if aggregation == 'monthly':
        df['period'] = df['date'].dt.to_period('M')
        df = df.groupby(['period', 'mode']).agg({
            'journeys_millions': 'sum',
            'indexed_value': 'mean',
        }).reset_index()
        df['date'] = df['period'].dt.to_timestamp()
        df = df.drop(columns=['period'])

    elif aggregation == 'quarterly':
        df['period'] = df['date'].dt.to_period('Q')
        df = df.groupby(['period', 'mode']).agg({
            'journeys_millions': 'sum',
            'indexed_value': 'mean',
        }).reset_index()
        df['date'] = df['period'].dt.to_timestamp()
        df = df.drop(columns=['period'])

    return df.sort_values(['date', 'mode'])


def register_callbacks(app: dash.Dash):
    """Register all Dash callbacks."""

    @app.callback(
        Output('main-chart', 'figure'),
        Output('summary-stats', 'children'),
        Input('mode-selector', 'value'),
        Input('view-type', 'value'),
        Input('aggregation', 'value'),
        Input('smoothing-toggle', 'value'),
        Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('data-refresh-trigger', 'data'),
    )
    def update_chart(modes, view_type, aggregation, smoothing, start_date, end_date, _):
        """Update the main chart based on selections."""

        if not modes:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title="Select at least one transport mode",
                xaxis_title="Date",
                yaxis_title="Journeys",
            )
            return empty_fig, "No data selected"

        # Parse dates
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.split('T')[0]).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.split('T')[0]).date()

        # Fetch data
        df = get_data(app.db_path, start_date, end_date, modes, aggregation)

        if df.empty:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                title="No data available. Click 'Load Sample Data' to get started.",
                xaxis_title="Date",
                yaxis_title="Journeys",
            )
            return empty_fig, "No data available"

        # Select value column
        y_col = 'indexed_value' if view_type == 'indexed' else 'journeys_millions'
        y_label = 'Index (100 = 2019 avg)' if view_type == 'indexed' else 'Journeys (millions)'

        # Apply smoothing if selected
        if 'rolling' in smoothing:
            df = df.sort_values(['mode', 'date'])
            df[y_col] = df.groupby('mode')[y_col].transform(
                lambda x: x.rolling(window=3, min_periods=1, center=True).mean()
            )

        # Create figure
        fig = go.Figure()

        for mode in modes:
            mode_df = df[df['mode'] == mode].sort_values('date')
            if mode_df.empty:
                continue

            config = MODE_CONFIG.get(mode, {'name': mode, 'color': '#888888'})

            fig.add_trace(go.Scatter(
                x=mode_df['date'],
                y=mode_df[y_col],
                name=config['name'],
                mode='lines+markers',
                line=dict(color=config['color'], width=2),
                marker=dict(size=4),
                hovertemplate=(
                    f"<b>{config['name']}</b><br>"
                    "Date: %{x|%b %Y}<br>"
                    f"{y_label}: %{{y:.1f}}<extra></extra>"
                ),
            ))

        # Add baseline reference line for indexed view
        if view_type == 'indexed':
            fig.add_hline(
                y=100,
                line_dash="dash",
                line_color="gray",
                annotation_text="2019 baseline",
                annotation_position="right"
            )

        fig.update_layout(
            title=f"London Transport Ridership ({aggregation.title()} View)",
            xaxis_title="Date",
            yaxis_title=y_label,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            template='plotly_white',
            margin=dict(l=60, r=20, t=80, b=60),
        )

        # Generate summary statistics
        summary = generate_summary_stats(df, modes, view_type)

        return fig, summary

    @app.callback(
        Output('date-range', 'start_date'),
        Output('date-range', 'end_date'),
        Input('btn-2019', 'n_clicks'),
        Input('btn-2022', 'n_clicks'),
        Input('btn-1y', 'n_clicks'),
        Input('btn-all', 'n_clicks'),
        prevent_initial_call=True,
    )
    def update_date_range(btn_2019, btn_2022, btn_1y, btn_all):
        """Update date range based on quick select buttons."""
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update, dash.no_update

        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        today = date.today()

        if button_id == 'btn-2019':
            return date(2019, 1, 1), date(2019, 12, 31)
        elif button_id == 'btn-2022':
            return date(2022, 1, 1), today
        elif button_id == 'btn-1y':
            return today - timedelta(days=365), today
        elif button_id == 'btn-all':
            return date(2019, 1, 1), today

        return dash.no_update, dash.no_update

    @app.callback(
        Output('data-status', 'children'),
        Output('data-refresh-trigger', 'data'),
        Input('btn-load-sample', 'n_clicks'),
        State('data-refresh-trigger', 'data'),
        prevent_initial_call=True,
    )
    def load_sample_data(n_clicks, current_trigger):
        """Load sample data into the database."""
        if not n_clicks:
            return dash.no_update, dash.no_update

        try:
            fetcher = TfLDataFetcher(app.db_path)
            inserted, updated = fetcher.load_sample_data()
            return (
                dbc.Alert(
                    f"Sample data loaded: {inserted} records inserted, {updated} updated",
                    color="success",
                    dismissable=True
                ),
                current_trigger + 1
            )
        except Exception as e:
            return (
                dbc.Alert(f"Error loading data: {str(e)}", color="danger", dismissable=True),
                current_trigger
            )

    @app.callback(
        Output('data-status', 'children', allow_duplicate=True),
        Output('data-refresh-trigger', 'data', allow_duplicate=True),
        Input('upload-csv', 'contents'),
        State('upload-csv', 'filename'),
        State('data-refresh-trigger', 'data'),
        prevent_initial_call=True,
    )
    def upload_csv(contents, filename, current_trigger):
        """Handle CSV file upload."""
        if contents is None:
            return dash.no_update, dash.no_update

        import base64
        from io import StringIO

        try:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            df = pd.read_csv(StringIO(decoded.decode('utf-8')))

            fetcher = TfLDataFetcher(app.db_path)
            parsed_df = fetcher.parse_tfl_datastore_format(df)
            inserted, updated = fetcher.import_data(parsed_df)

            return (
                dbc.Alert(
                    f"Uploaded {filename}: {inserted} records inserted, {updated} updated",
                    color="success",
                    dismissable=True
                ),
                current_trigger + 1
            )
        except Exception as e:
            return (
                dbc.Alert(f"Error uploading file: {str(e)}", color="danger", dismissable=True),
                current_trigger
            )

    @app.callback(
        Output('download-csv', 'data'),
        Output('export-status', 'children'),
        Input('btn-export', 'n_clicks'),
        State('mode-selector', 'value'),
        State('date-range', 'start_date'),
        State('date-range', 'end_date'),
        State('aggregation', 'value'),
        prevent_initial_call=True,
    )
    def export_csv(n_clicks, modes, start_date, end_date, aggregation):
        """Export current view to CSV."""
        if not n_clicks or not modes:
            return dash.no_update, "Select modes to export"

        # Parse dates
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.split('T')[0]).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.split('T')[0]).date()

        df = get_data(app.db_path, start_date, end_date, modes, aggregation)

        if df.empty:
            return dash.no_update, "No data to export"

        # Add mode display names
        df['mode_name'] = df['mode'].map(lambda x: MODE_CONFIG.get(x, {}).get('name', x))

        filename = f"uk_mobility_data_{start_date}_{end_date}.csv"

        return (
            dcc.send_data_frame(df.to_csv, filename, index=False),
            f"Exported {len(df)} records"
        )


def generate_summary_stats(df: pd.DataFrame, modes: List[str], view_type: str) -> html.Div:
    """Generate summary statistics cards."""
    if df.empty:
        return html.P("No data available")

    cards = []
    y_col = 'indexed_value' if view_type == 'indexed' else 'journeys_millions'

    for mode in modes:
        mode_df = df[df['mode'] == mode]
        if mode_df.empty:
            continue

        config = MODE_CONFIG.get(mode, {'name': mode, 'color': '#888888'})

        # Calculate stats
        latest = mode_df.sort_values('date').iloc[-1]
        avg_val = mode_df[y_col].mean()
        min_val = mode_df[y_col].min()
        max_val = mode_df[y_col].max()

        # Calculate trend (compare last 3 periods to previous 3)
        sorted_df = mode_df.sort_values('date')
        if len(sorted_df) >= 6:
            recent_avg = sorted_df[y_col].iloc[-3:].mean()
            prior_avg = sorted_df[y_col].iloc[-6:-3].mean()
            trend_pct = ((recent_avg - prior_avg) / prior_avg * 100) if prior_avg > 0 else 0
            trend_text = f"+{trend_pct:.1f}%" if trend_pct > 0 else f"{trend_pct:.1f}%"
            trend_color = "success" if trend_pct > 0 else "danger"
        else:
            trend_text = "N/A"
            trend_color = "secondary"

        unit = '' if view_type == 'indexed' else 'M'

        card = dbc.Card([
            dbc.CardHeader(
                config['name'],
                style={'backgroundColor': config['color'], 'color': 'white', 'fontWeight': 'bold'}
            ),
            dbc.CardBody([
                html.P([
                    html.Strong("Latest: "),
                    f"{latest[y_col]:.1f}{unit}"
                ], className="mb-1"),
                html.P([
                    html.Strong("Average: "),
                    f"{avg_val:.1f}{unit}"
                ], className="mb-1"),
                html.P([
                    html.Strong("Range: "),
                    f"{min_val:.1f} - {max_val:.1f}{unit}"
                ], className="mb-1"),
                html.P([
                    html.Strong("Trend: "),
                    dbc.Badge(trend_text, color=trend_color)
                ], className="mb-0"),
            ])
        ], className="h-100")

        cards.append(dbc.Col(card, md=3, className="mb-3"))

    return dbc.Row(cards)


# Entry point for running the app directly
def run_dashboard(debug: bool = True, port: int = 8050):
    """Run the dashboard application."""
    app = create_app()
    app.run(debug=debug, port=port)


if __name__ == '__main__':
    run_dashboard()
