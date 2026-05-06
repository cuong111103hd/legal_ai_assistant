import re

with open("frontend/client/pages/ContractReview.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# We want to replace the wrapper.
# Find: `<div className="flex-1 overflow-y-auto p-8">\n          <div className="max-w-5xl mx-auto space-y-8">\n            {/* Upload Area */}\n            {!result && !isUploading && (`
# Replace with: `{(!result) ? (\n          <div className="flex-1 overflow-y-auto p-8">\n            <div className="max-w-5xl mx-auto space-y-8">\n              {/* Upload Area */}\n              {!isUploading && (`

content = content.replace(
    """        <div className="flex-1 overflow-y-auto p-8">
          <div className="max-w-5xl mx-auto space-y-8">
            {/* Upload Area */}
            {!result && !isUploading && (""",
    """        {!result ? (
          <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-5xl mx-auto space-y-8">
              {/* Upload Area */}
              {!isUploading && ("""
)

# Now find the transition between Loading and Result.
# Find: `            {/* Results Display */}\n            {result && (\n              <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 space-y-8 pb-12">\n                {/* Overall Summary Card */}`
# Replace with: `            </div>\n          </div>\n        ) : (\n          <div className="flex-1 flex overflow-hidden">\n            {/* Left Pane: Original Text */}\n            <div className="flex-1 overflow-y-auto p-8 bg-white border-r border-slate-200">\n               <div className="max-w-3xl mx-auto">\n                 <h2 className="text-xl font-bold mb-6 text-slate-900 sticky top-0 bg-white/90 backdrop-blur pb-4 border-b z-10">\n                    Toàn văn Hợp đồng\n                 </h2>\n                 <div className="whitespace-pre-wrap font-serif text-slate-800 leading-relaxed text-base">\n                   {contractText}\n                 </div>\n               </div>\n            </div>\n\n            {/* Right Pane: Analysis */}\n            <div className="w-[500px] flex-shrink-0 overflow-y-auto bg-slate-50 p-6 shadow-[-4px_0_15px_rgba(0,0,0,0.02)] z-10 relative">\n               <div className="animate-in fade-in slide-in-from-right-8 duration-700 space-y-8 pb-12">\n                {/* Overall Summary Card */}`

content = content.replace(
    """            {/* Results Display */}
            {result && (
              <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 space-y-8 pb-12">
                {/* Overall Summary Card */}""",
    """            </div>
          </div>
        ) : (
          <div className="flex-1 flex overflow-hidden">
            {/* Left Pane: Original Text */}
            <div className="flex-1 overflow-y-auto p-8 bg-white border-r border-slate-200">
               <div className="max-w-3xl mx-auto relative">
                 <h2 className="text-xl font-bold mb-6 text-slate-900 sticky top-0 bg-white/90 backdrop-blur pb-4 border-b z-10">
                    Toàn văn Hợp đồng
                 </h2>
                 <div className="whitespace-pre-wrap font-serif text-slate-800 leading-relaxed text-base">
                   {contractText}
                 </div>
               </div>
            </div>

            {/* Right Pane: Analysis */}
            <div className="w-[550px] flex-shrink-0 overflow-y-auto bg-slate-50 p-6 shadow-[-4px_0_15px_rgba(0,0,0,0.02)] z-10 relative">
               <div className="animate-in fade-in slide-in-from-right-8 duration-700 space-y-8 pb-12">
                {/* Overall Summary Card */}"""
)

# And close the tags at the end.
# We need to change the final `            )}` and `          </div>\n        </div>` to just `            </div>\n          </div>\n        )}`
content = content.replace(
    """              </div>
            )}
          </div>
        </div>
      </div>

      {/* Document Viewer Overlay */}""",
    """              </div>
            </div>
          </div>
        )}
      </div>

      {/* Document Viewer Overlay */}"""
)

# Also fix the grid layout inside the Analysis so it fits 550px instead of going full width with 2 columns.
# Currently: `                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">`
# We want to change it to: `                          <div className="flex flex-col gap-6 mt-2">`
content = content.replace(
    """                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">""",
    """                          <div className="flex flex-col gap-6 mt-2">"""
)

# And the overall risks grid: `                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">`
# Change to `                  <div className="flex flex-col gap-4">`
content = content.replace(
    """                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">""",
    """                  <div className="flex flex-col gap-4">"""
)

with open("frontend/client/pages/ContractReview.tsx", "w", encoding="utf-8") as f:
    f.write(content)

print("Modified ContractReview.tsx successfully.")
