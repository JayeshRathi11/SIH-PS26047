import React, { useState } from 'react';
import { Users, AlertTriangle, Clock, RefreshCw, UserCheck, Search, Filter } from 'lucide-react';

export default function QueueSidebar({
  queue = [],
  selectedPatientId,
  onSelectPatient,
  onRefresh,
  isLoading = false
}) {
  const [filter, setFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  const filteredQueue = queue.filter(item => {
    const matchesFilter =
      filter === 'ALL' ||
      (filter === 'RED_FLAG' && item.is_red_flag) ||
      (filter === 'WAITING' && item.status === 'WAITING') ||
      (filter === 'IN_PROGRESS' && item.status === 'IN_PROGRESS');

    const patientName = item.patient?.name?.toLowerCase() || '';
    const token = item.queue_number?.toString() || '';
    const matchesSearch = patientName.includes(searchTerm.toLowerCase()) || token.includes(searchTerm);

    return matchesFilter && matchesSearch;
  });

  return (
    <aside className="w-full md:w-80 lg:w-96 bg-white border-r border-stone-200 flex flex-col h-full shrink-0">
      {/* Sidebar Header */}
      <div className="p-4 border-b border-stone-200 bg-stone-50/80">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-ayush-primary" />
            <h3 className="font-bold text-stone-800 text-base">OPD Queue</h3>
            <span className="bg-ayush-primary/10 text-ayush-primary text-xs px-2 py-0.5 rounded-full font-bold">
              {queue.length}
            </span>
          </div>

          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="p-1.5 rounded-lg border border-stone-200 hover:bg-stone-100 text-stone-600 transition disabled:opacity-50"
            title="Refresh Queue"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-ayush-primary' : ''}`} />
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-2">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
          <input
            type="text"
            placeholder="Search patient or token..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-stone-200 focus:outline-none focus:ring-1 focus:ring-ayush-primary bg-white"
          />
        </div>

        {/* Status Filters */}
        <div className="flex gap-1">
          {['ALL', 'WAITING', 'RED_FLAG'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`flex-1 py-1 px-2 text-[11px] font-semibold rounded-md transition ${
                filter === f
                  ? 'bg-ayush-primary text-white shadow-xs'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              {f === 'ALL' ? 'All' : f === 'WAITING' ? 'Waiting' : '⚠️ Red Flags'}
            </button>
          ))}
        </div>
      </div>

      {/* Queue Items List */}
      <div className="flex-1 overflow-y-auto divide-y divide-stone-100 p-2 space-y-1">
        {filteredQueue.length === 0 ? (
          <div className="p-8 text-center text-xs text-stone-400">
            No patients found matching the criteria.
          </div>
        ) : (
          filteredQueue.map((item) => {
            const isSelected = selectedPatientId === item.patient_id || selectedPatientId === item.id;
            const isElderly = item.patient?.age >= 65;

            return (
              <div
                key={item.id}
                onClick={() => onSelectPatient(item)}
                className={`p-3 rounded-xl cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-emerald-50/80 border-2 border-ayush-primary shadow-xs'
                    : 'bg-white hover:bg-stone-50 border border-transparent'
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold bg-stone-100 px-2 py-0.5 rounded text-stone-700">
                      #{item.queue_number || item.id?.slice(0, 4)}
                    </span>
                    <span className="font-bold text-sm text-stone-900 truncate">
                      {item.patient?.name || 'Patient'}
                    </span>
                  </div>

                  {item.priority_score !== undefined && (
                    <span
                      title="Calculated Priority Score"
                      className={`text-[11px] font-mono px-1.5 py-0.5 rounded font-bold ${
                        item.priority_score >= 1000
                          ? 'bg-rose-100 text-rose-800'
                          : item.priority_score >= 50
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-stone-100 text-stone-600'
                      }`}
                    >
                      P:{Math.round(item.priority_score)}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2 text-xs text-stone-500 mb-2">
                  <span>{item.patient?.age || '--'} Y • {item.patient?.gender || '--'}</span>
                  {isElderly && (
                    <span className="bg-purple-100 text-purple-700 text-[10px] px-1.5 py-0.2 rounded font-semibold">
                      Senior (65+)
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between text-[11px]">
                  <div className="flex items-center gap-1.5">
                    {item.is_red_flag && (
                      <span className="inline-flex items-center gap-1 bg-rose-50 text-rose-700 border border-rose-200 px-1.5 py-0.5 rounded font-bold">
                        <AlertTriangle className="w-3 h-3" />
                        RED FLAG
                      </span>
                    )}
                    <span
                      className={`px-1.5 py-0.5 rounded font-medium ${
                        item.status === 'WAITING'
                          ? 'bg-amber-50 text-amber-700'
                          : item.status === 'IN_PROGRESS'
                          ? 'bg-blue-50 text-blue-700'
                          : 'bg-stone-100 text-stone-600'
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>

                  <span className="text-stone-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {item.wait_time_minutes ? `${item.wait_time_minutes}m` : 'Just now'}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
